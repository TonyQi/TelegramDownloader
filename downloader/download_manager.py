import asyncio
import uuid
from collections import deque
from pathlib import Path
from threading import RLock

from config import CHUNK_SIZE
from core.database import db
from downloader.chunk_downloader import ChunkDownloader
from downloader.resume_store import clear_meta, load_meta, save_meta
from downloader.speed_tracker import SpeedTracker
from models.task import DownloadTask
from telegram.link_parser import parse_message_link


class DownloadManager:
    def __init__(self, telegram_service, settings_manager):
        self.telegram_service = telegram_service
        self.settings_manager = settings_manager

        self.tasks = {}
        self.lock = RLock()

        # 显式任务队列
        self.waiting_queue = deque()

        # 当前运行中的 task_id
        self.running_tasks = set()

        # task_id -> concurrent.futures.Future
        self.task_futures = {}

        self.max_concurrent_tasks = max(
            1, int(self.settings_manager.get("max_concurrent_tasks", 3))
        )
        self._load_tasks_from_db()
        self._schedule_next()

    def refresh_limits(self):
        with self.lock:
            self.max_concurrent_tasks = max(
                1, int(self.settings_manager.get("max_concurrent_tasks", 3))
            )
        self._schedule_next()

    def shutdown(self):
        db.close()

    def add_task(self, url: str) -> DownloadTask:
        task_id = str(uuid.uuid4())
        task = DownloadTask(task_id=task_id, url=url)
        task.set_status("queued")

        with self.lock:
            self.tasks[task_id] = task
            self.waiting_queue.append(task_id)

        db.upsert_task(task)
        self._schedule_next()
        return task

    def add_message_task(self, chat_ref: str, message_id: int) -> DownloadTask:
        return self.add_task(f"tg://message/{chat_ref}/{int(message_id)}")

    def list_tasks(self):
        with self.lock:
            return list(self.tasks.values())

    def get_task(self, task_id: str):
        with self.lock:
            return self.tasks.get(task_id)

    def pause_task(self, task_id: str):
        task = self.get_task(task_id)
        if not task:
            return

        with self.lock:
            if task.status == "queued":
                task.set_status("paused")
                try:
                    self.waiting_queue.remove(task_id)
                except ValueError:
                    pass
                db.upsert_task(task)
                return

            task.pause_event.set()
            task.set_status("paused")
            db.upsert_task(task)

    def resume_task(self, task_id: str):
        task = self.get_task(task_id)
        if not task:
            return

        with self.lock:
            if task.status == "finished":
                return
            if (
                task.total_size > 0
                and task.file_path
                and Path(task.file_path).exists()
                and Path(task.file_path).stat().st_size >= task.total_size
            ):
                clear_meta(task.file_path)
                task.update_progress(task.total_size, task.total_size, 0.0)
                task.set_status("finished")
                db.upsert_task(task)
                return

            task.pause_event.clear()
            task.cancel_event.clear()

            if task.status in ("paused", "failed"):
                task.set_status("queued")

                # 防止重复入队
                if (
                        task_id not in self.running_tasks
                        and task_id not in self.waiting_queue
                ):
                    self.waiting_queue.append(task_id)

            db.upsert_task(task)

        self._schedule_next()

    def cancel_task(self, task_id: str):
        task = self.get_task(task_id)
        if not task:
            return

        with self.lock:
            task.cancel_event.set()

            if task.status == "queued":
                task.set_status("cancelled")
                try:
                    self.waiting_queue.remove(task_id)
                except ValueError:
                    pass
                db.upsert_task(task)
                return

            task.set_status("cancelled")
            db.upsert_task(task)

    def _schedule_next(self):
        """
        只要有空闲槽位，就从 waiting_queue 里启动新任务
        """
        with self.lock:
            while (
                    len(self.running_tasks) < self.max_concurrent_tasks
                    and self.waiting_queue
            ):
                task_id = self.waiting_queue.popleft()
                task = self.tasks.get(task_id)

                if not task:
                    continue

                if task.status not in ("queued", "waiting"):
                    continue

                task.set_status("downloading")
                db.upsert_task(task)

                self.running_tasks.add(task_id)

                fut = self.telegram_service.submit(self._run_task(task))
                self.task_futures[task_id] = fut
                fut.add_done_callback(
                    lambda f, tid=task_id: self._on_task_done(tid, f)
                )

    def _on_task_done(self, task_id, future):
        with self.lock:
            self.running_tasks.discard(task_id)
            self.task_futures.pop(task_id, None)

            task = self.tasks.get(task_id)
            if task:
                # 如果协程异常结束，兜底标记
                try:
                    future.result()
                except Exception as exc:
                    if task.status not in ("cancelled", "paused", "finished"):
                        task.set_status("failed")
                        task.set_error(str(exc))
                        db.upsert_task(task)

        # 某个任务结束后，继续调度排队任务
        self._schedule_next()

    async def _run_task(self, task: DownloadTask):
        try:
            chat, message_id = self._parse_task_target(task.url)
        except Exception as exc:
            task.set_status("failed")
            task.set_error(str(exc))
            db.upsert_task(task)
            return

        try:
            if task.cancel_event.is_set():
                task.set_status("cancelled")
                db.upsert_task(task)
                return

            if isinstance(chat, str) and task.url.startswith("tg://message/"):
                chat = await self.telegram_service.resolve_entity(chat)

            msg = await self.telegram_service.client.get_messages(chat, ids=message_id)
            if not msg or not getattr(msg, "document", None):
                raise ValueError("消息中没有可下载的 document 文件")

            task.name = msg.file.name or f"{task.task_id}.bin"
            task.total_size = msg.file.size or 0

            download_dir = self.settings_manager.ensure_download_dir()
            file_path = str(Path(download_dir) / task.name)
            task.file_path = file_path

            path_obj = Path(file_path)
            if task.total_size and path_obj.exists() and path_obj.stat().st_size >= task.total_size:
                clear_meta(file_path)
                task.update_progress(task.total_size, task.total_size, 0.0)
                task.set_status("finished")
                db.upsert_task(task)
                return

            if not path_obj.exists():
                with open(path_obj, "wb") as f:
                    f.truncate(task.total_size)

            meta = load_meta(file_path)
            completed = set(int(i) for i in meta.get("downloaded_chunks", []))

            task.downloaded_size = sum(
                min(CHUNK_SIZE, max(task.total_size - offset, 0))
                for offset in range(0, task.total_size, CHUNK_SIZE)
                if (offset // CHUNK_SIZE) in completed
            )
            task.progress = (
                task.downloaded_size / task.total_size * 100.0
                if task.total_size else 0.0
            )

            if task.cancel_event.is_set():
                task.set_status("cancelled")
                db.upsert_task(task)
                return

            if task.pause_event.is_set():
                task.set_status("paused")
                db.upsert_task(task)
                return

            task.set_status("downloading")
            db.upsert_task(task)

            downloader = ChunkDownloader(
                self.telegram_service.client,
                msg.document,
                file_path
            )
            speed_tracker = SpeedTracker()
            chunk_concurrency = max(
                1, int(self.settings_manager.get("chunk_concurrency", 4))
            )

            queue = asyncio.Queue()
            for offset in range(0, task.total_size, CHUNK_SIZE):
                if (offset // CHUNK_SIZE) not in completed:
                    queue.put_nowait(offset)

            update_lock = asyncio.Lock()

            async def worker():
                while True:
                    if task.cancel_event.is_set():
                        return

                    # 暂停时直接退出当前任务，让出并发槽位
                    if task.pause_event.is_set():
                        task.set_status("paused")
                        db.upsert_task(task)
                        return

                    try:
                        offset = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return

                    try:
                        size = await downloader.download_chunk(offset)
                    finally:
                        queue.task_done()

                    chunk_id = offset // CHUNK_SIZE

                    async with update_lock:
                        completed.add(chunk_id)
                        meta["downloaded_chunks"] = sorted(completed)
                        save_meta(file_path, meta)

                        task.downloaded_size += size
                        speed_tracker.add(size)
                        task.update_progress(
                            task.downloaded_size,
                            task.total_size,
                            speed_tracker.get_speed(),
                        )

                        if not task.pause_event.is_set() and not task.cancel_event.is_set():
                            task.set_status("downloading")

                        db.upsert_task(task)

            workers = [asyncio.create_task(worker()) for _ in range(chunk_concurrency)]

            try:
                await asyncio.gather(*workers)
            finally:
                await downloader.close()

            if task.cancel_event.is_set():
                task.set_status("cancelled")
            elif task.pause_event.is_set():
                task.set_status("paused")
            elif task.downloaded_size >= task.total_size:
                clear_meta(file_path)
                task.update_progress(task.total_size, task.total_size, 0.0)
                task.set_status("finished")
            else:
                task.set_status("paused")

            db.upsert_task(task)

        except Exception as exc:
            task.set_status("failed")
            task.set_error(str(exc))
            db.upsert_task(task)

    @staticmethod
    def _parse_task_target(url: str):
        prefix = "tg://message/"
        if url.startswith(prefix):
            rest = url[len(prefix):]
            chat_ref, sep, message_id = rest.rpartition("/")
            if not sep or not chat_ref or not message_id:
                raise ValueError("Invalid internal Telegram message reference")
            return chat_ref, int(message_id)

        return parse_message_link(url)

    def _load_tasks_from_db(self):
        saved_tasks = db.list_tasks()
        with self.lock:
            for task in saved_tasks:
                # 程序重启后，原先“下载中”的任务实际上已经中断
                if task.status == "downloading":
                    task.set_status("paused")
                    task.speed = 0.0

                # 排队中的任务可以继续保留在队列里
                if task.status == "queued":
                    task.speed = 0.0

                # 暂停状态保留
                if task.status == "paused":
                    task.speed = 0.0

                # finished / failed / cancelled 保持原样，但速度清零更合理
                if task.status in ("finished", "failed", "cancelled"):
                    task.speed = 0.0

                self.tasks[task.task_id] = task

                # 只有 queued 的任务启动时自动重新排队
                if task.status == "queued":
                    self.waiting_queue.append(task.task_id)

                db.upsert_task(task)

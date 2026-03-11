import asyncio
import base64
import io
from concurrent.futures import Future
from threading import Event, Thread

import qrcode
from telethon import TelegramClient

from config import API_HASH, API_ID, SESSION_FILE, SESSIONS_DIR
from core.proxy import build_telethon_proxy


class TelegramService:
    def __init__(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

        self.loop = None
        self.thread = None
        self.client = None

        self._started = False
        self._qr_login = None
        self._qr_wait_task = None

        self._loop_ready = Event()
        self._connect_ready = Event()
        self._connect_error = None

    def _build_client(self):
        return TelegramClient(
            str(SESSION_FILE),
            API_ID,
            API_HASH,
            proxy=build_telethon_proxy(),
        )

    def start(self):
        if self._started:
            return

        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        if not self._loop_ready.wait(timeout=10):
            raise RuntimeError("Telegram event loop start timeout")

        if not self._connect_ready.wait(timeout=30):
            if self._connect_error is not None:
                raise RuntimeError(f"Telegram connect failed: {self._connect_error}")
            raise RuntimeError("Telegram connect timeout")

        self._started = True

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.client = self._build_client()
        self._loop_ready.set()

        async def init():
            try:
                await self.client.connect()
                self._connect_ready.set()
            except Exception as e:
                self._connect_error = e
                self._connect_ready.set()

        self.loop.create_task(init())

        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()

            if pending:
                try:
                    self.loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except Exception:
                    pass

            self.loop.close()

    def submit(self, coro) -> Future:
        if not self.loop:
            raise RuntimeError("TelegramService not started")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def call(self, coro, timeout=None):
        return self.submit(coro).result(timeout=timeout)

    async def _ensure_connected(self):
        if self.client is None:
            self.client = self._build_client()

        if not self.client.is_connected():
            await self.client.connect()

    async def _is_authorized(self):
        if not self.client:
            return False

        try:
            await self._ensure_connected()
        except Exception:
            return False

        return await self.client.is_user_authorized()

    def is_authorized(self, timeout=None) -> bool:
        return bool(self.call(self._is_authorized(), timeout=timeout))

    async def _recreate_client(self):
        old_client = self.client

        if old_client is not None:
            try:
                if old_client.is_connected():
                    await old_client.disconnect()
            except Exception:
                pass

        self.client = self._build_client()
        await self.client.connect()

    async def _logout(self):
        old_client = self.client

        if old_client is not None:
            try:
                if not old_client.is_connected():
                    await old_client.connect()
                await old_client.log_out()
            except Exception:
                pass

            try:
                if old_client.is_connected():
                    await old_client.disconnect()
            except Exception:
                pass

        self._qr_login = None

        if self._qr_wait_task and not self._qr_wait_task.done():
            self._qr_wait_task.cancel()
            try:
                await self._qr_wait_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        self._qr_wait_task = None

        # logout 后必须重建 client，旧实例不能复用
        self.client = self._build_client()
        await self.client.connect()

    def logout(self):
        return self.call(self._logout(), timeout=30)

    async def _generate_qr(self):
        await self._ensure_connected()

        if await self.client.is_user_authorized():
            return {"status": "authorized", "image_base64": ""}

        self._qr_login = await self.client.qr_login()

        image = qrcode.make(self._qr_login.url)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        if self._qr_wait_task and not self._qr_wait_task.done():
            self._qr_wait_task.cancel()
            try:
                await self._qr_wait_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        self._qr_wait_task = asyncio.create_task(self._wait_qr_login())

        return {
            "status": "scan",
            "image_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }

    async def _wait_qr_login(self):
        try:
            await self._qr_login.wait()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def generate_qr(self):
        return self.call(self._generate_qr(), timeout=30)

    async def _stop(self):
        try:
            if self._qr_wait_task and not self._qr_wait_task.done():
                self._qr_wait_task.cancel()
                try:
                    await self._qr_wait_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            if self.client and self.client.is_connected():
                await self.client.disconnect()
        finally:
            self.loop.stop()

    def stop(self):
        if not self._started or not self.loop:
            return

        fut = self.submit(self._stop())
        try:
            fut.result(timeout=10)
        except Exception:
            pass

        if self.thread:
            self.thread.join(timeout=10)

        self._started = False
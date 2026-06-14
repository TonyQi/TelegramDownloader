import asyncio
import base64
import io
from concurrent.futures import Future
from threading import Event, Thread

import qrcode
from telethon import TelegramClient
from telethon import events
from telethon import utils
from telethon.sessions import StringSession
from telethon.tl.functions.help import GetConfigRequest

from config import API_HASH, API_ID, SESSION_FILE, SESSIONS_DIR
from core.cache_store import cache_store
from core.proxy import build_telethon_proxy


class TelegramService:
    def __init__(self, settings_manager=None):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.settings_manager = settings_manager

        self.loop = None
        self.thread = None
        self.client = None

        self._started = False
        self._qr_login = None
        self._qr_wait_task = None
        self._dialog_entities = {}
        self._message_handlers = []
        self._new_message_handler = None

        # 原始 Telethon 消息对象缓存，用于缩略图直接下载，
        # 避免 _message_thumbnail_base64() 重新调用 get_messages()
        self._raw_message_cache = {}  # {(chat_ref, message_id): Telethon Message}

        self._loop_ready = Event()
        self._connect_ready = Event()
        self._connect_error = None

    def _build_client(self):
        proxy_settings = None
        if self.settings_manager is not None:
            proxy_settings = self.settings_manager.get("proxy")

        return TelegramClient(
            str(SESSION_FILE),
            API_ID,
            API_HASH,
            proxy=build_telethon_proxy(proxy_settings),
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
                self._install_event_handlers()
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

    @staticmethod
    def _is_transient_network_error(exc):
        text = str(exc).lower()
        transient_markers = (
            "server closed the connection",
            "connection closed",
            "connection reset",
            "connection aborted",
            "incomplete",
            "read on a total",
            "timed out",
            "timeout",
        )
        return isinstance(
            exc,
            (
                ConnectionError,
                OSError,
                asyncio.TimeoutError,
                asyncio.IncompleteReadError,
            ),
        ) or any(marker in text for marker in transient_markers)

    async def _reconnect_after_transient_error(self):
        if self.client is None:
            return
        try:
            await self.client.disconnect()
        except Exception:
            pass
        await asyncio.sleep(0.8)
        try:
            await self.client.connect()
        except Exception:
            pass

    def _install_event_handlers(self):
        if self.client is None or self._new_message_handler is not None:
            return

        async def handle_new_message(event):
            try:
                chat = await event.get_chat()
                message = await self._message_to_dict(event.message)
                message["chat_id"] = str(utils.get_peer_id(chat))
                cache_store.merge_messages(message["chat_id"], [message])
            except Exception:
                return

            for handler in list(self._message_handlers):
                try:
                    handler(message)
                except Exception:
                    pass

        self._new_message_handler = handle_new_message
        self.client.add_event_handler(handle_new_message, events.NewMessage)

    def add_message_handler(self, handler):
        if handler not in self._message_handlers:
            self._message_handlers.append(handler)

    def remove_message_handler(self, handler):
        try:
            self._message_handlers.remove(handler)
        except ValueError:
            pass

    def _cache_entity(self, entity):
        key = str(utils.get_peer_id(entity))
        self._dialog_entities[key] = entity
        return key

    async def resolve_entity(self, chat_ref):
        await self._ensure_connected()
        key = str(chat_ref)
        if key in self._dialog_entities:
            return self._dialog_entities[key]

        try:
            entity = await self.client.get_entity(int(key))
        except (TypeError, ValueError):
            entity = await self.client.get_entity(chat_ref)

        self._cache_entity(entity)
        return entity

    @staticmethod
    def _file_info(message):
        if not getattr(message, "file", None):
            return None
        return {
            "name": message.file.name or f"{message.id}.bin",
            "size": int(message.file.size or 0),
            "mime_type": message.file.mime_type or "",
        }

    @staticmethod
    def _media_kind(message):
        if getattr(message, "photo", None):
            return "photo"

        file_info = getattr(message, "file", None)
        if file_info and file_info.mime_type:
            if file_info.mime_type.startswith("image/"):
                return "photo"
            if file_info.mime_type.startswith("video/"):
                return "video"

        return ""

    async def _thumbnail_bytes(self, message, timeout=3):
        if not (getattr(message, "photo", None) or getattr(message, "document", None)):
            return b""

        try:
            # thumb=-1 请求最大可用缩略图，清晰度最佳；
            # 速度由并发分批和原始消息缓存保证，不再靠缩小尺寸
            data = await asyncio.wait_for(
                self.client.download_media(message, file=bytes, thumb=-1),
                timeout=timeout,
            )
        except (asyncio.TimeoutError, Exception):
            return b""

        return data or b""

    async def _thumbnail_base64(self, message, timeout=3):
        data = await self._thumbnail_bytes(message, timeout=timeout)
        if not data:
            return ""

        return base64.b64encode(data).decode("ascii")

    async def _avatar_base64(self, entity, dialog_id, fetch_remote=True):
        cached = cache_store.load_avatar_base64(dialog_id)
        if cached:
            return cached
        if not fetch_remote:
            return ""

        try:
            data = await asyncio.wait_for(
                self.client.download_profile_photo(entity, file=bytes),
                timeout=4,
            )
        except (asyncio.TimeoutError, Exception):
            return ""

        if not data:
            return ""

        cache_store.save_avatar(dialog_id, data)
        return base64.b64encode(data).decode("ascii")

    async def _message_to_dict(self, message, include_thumbnail=True):
        text = message.message or ""
        file_info = self._file_info(message)
        media_kind = self._media_kind(message)
        thumbnail = ""
        if include_thumbnail and media_kind in ("photo", "video"):
            thumbnail = await self._thumbnail_base64(message)

        return {
            "id": int(message.id),
            "grouped_id": str(message.grouped_id or ""),
            "date": message.date.astimezone().strftime("%Y-%m-%d %H:%M")
            if message.date
            else "",
            "text": text,
            "out": bool(message.out),
            "sender_id": str(message.sender_id or ""),
            "has_document": bool(getattr(message, "document", None)),
            "file": file_info,
            "media_kind": media_kind,
            "thumbnail_base64": thumbnail,
        }

    @staticmethod
    def _group_album_messages(messages):
        grouped = []
        albums = {}

        for message in messages:
            grouped_id = message.get("grouped_id")
            if not grouped_id:
                grouped.append(message)
                continue

            album = albums.get(grouped_id)
            if album is None:
                album = {
                    "id": message["id"],
                    "grouped_id": grouped_id,
                    "date": message["date"],
                    "text": "",
                    "out": message["out"],
                    "sender_id": message["sender_id"],
                    "has_document": False,
                    "file": None,
                    "media_kind": "album",
                    "thumbnail_base64": "",
                    "media_items": [],
                }
                albums[grouped_id] = album
                grouped.append(album)

            if message.get("text") and not album["text"]:
                album["text"] = message["text"]
            if message.get("has_document"):
                album["has_document"] = True
                if album["file"] is None:
                    album["file"] = message.get("file")

            album["media_items"].append(
                {
                    "id": message["id"],
                    "media_kind": message.get("media_kind", ""),
                    "file": message.get("file"),
                    "thumbnail_base64": message.get("thumbnail_base64", ""),
                    "has_document": message.get("has_document", False),
                }
            )

        return grouped

    async def _list_dialogs(self, limit=80):
        await self._ensure_connected()
        dialogs = []
        missing_avatars = []
        async for dialog in self.client.iter_dialogs(limit=limit):
            key = self._cache_entity(dialog.entity)
            avatar = await self._avatar_base64(dialog.entity, key, fetch_remote=False)
            dialogs.append(
                {
                    "id": key,
                    "title": dialog.name or "Untitled",
                    "unread_count": int(dialog.unread_count or 0),
                    "pinned": bool(dialog.pinned),
                    "avatar_base64": avatar,
                }
            )
            if not avatar:
                missing_avatars.append((len(dialogs) - 1, dialog.entity, key))

        avatar_semaphore = asyncio.Semaphore(8)

        async def fill_avatar(index, entity, key):
            async with avatar_semaphore:
                dialogs[index]["avatar_base64"] = await self._avatar_base64(
                    entity,
                    key,
                    fetch_remote=True,
                )

        if missing_avatars:
            await asyncio.gather(
                *[
                    fill_avatar(index, entity, key)
                    for index, entity, key in missing_avatars
                ],
                return_exceptions=True,
            )

        cache_store.save_dialogs(dialogs)
        return dialogs

    def list_dialogs(self, limit=80, timeout=30):
        return self.call(self._list_dialogs(limit=limit), timeout=timeout)

    def list_dialogs_async(self, limit=80):
        return self.submit(self._list_dialogs(limit=limit))

    def list_dialogs_cached(self):
        return cache_store.load_dialogs()

    def _hydrate_cached_thumbnails(self, chat_ref, messages):
        for message in messages:
            media_items = message.get("media_items") or []
            if media_items:
                for media in media_items:
                    if media.get("thumbnail_base64"):
                        continue
                    media["thumbnail_base64"] = cache_store.load_thumbnail_base64(
                        chat_ref,
                        media.get("id"),
                    )
                continue

            if message.get("thumbnail_base64"):
                continue
            if message.get("media_kind") in ("photo", "video"):
                message["thumbnail_base64"] = cache_store.load_thumbnail_base64(
                    chat_ref,
                    message.get("id"),
                )
        return messages

    async def _collect_raw_messages(
        self,
        chat_ref,
        limit=60,
        offset_id=0,
        min_id=0,
        reverse=False,
    ):
        last_error = None
        for attempt in range(2):
            try:
                entity = await self.resolve_entity(chat_ref)
                kwargs = {"limit": limit}
                if offset_id:
                    kwargs["offset_id"] = int(offset_id or 0)
                if min_id:
                    kwargs["min_id"] = int(min_id or 0)
                    kwargs["reverse"] = bool(reverse)

                raw_messages = []
                async for message in self.client.iter_messages(entity, **kwargs):
                    raw_messages.append(message)
                return raw_messages
            except Exception as exc:
                last_error = exc
                if attempt == 0 and self._is_transient_network_error(exc):
                    await self._reconnect_after_transient_error()
                    continue
                raise

        if last_error:
            raise last_error
        return []

    async def _list_messages(
        self,
        chat_ref,
        limit=60,
        include_thumbnails=True,
        offset_id=0,
    ):
        raw_messages = await self._collect_raw_messages(
            chat_ref,
            limit=limit,
            offset_id=int(offset_id or 0),
        )

        if not raw_messages:
            return []

        # 将原始 Telethon 消息对象缓存起来，后续缩略图下载可直接使用，
        # 避免 _message_thumbnail_base64() 再次调用 get_messages()
        chat_key = str(chat_ref)
        for msg in raw_messages:
            self._raw_message_cache[(chat_key, int(msg.id))] = msg

        # 阶段二：并发下载所有缩略图
        if include_thumbnails:
            thumb_concurrency = 16

            async def to_dict_with_thumb(msg):
                return await self._message_to_dict(msg, include_thumbnail=True)

            # 分批并发，避免同时建立过多连接
            results = []
            for i in range(0, len(raw_messages), thumb_concurrency):
                batch = raw_messages[i:i + thumb_concurrency]
                batch_results = await asyncio.gather(
                    *[to_dict_with_thumb(m) for m in batch],
                    return_exceptions=True,
                )
                for msg, res in zip(batch, batch_results):
                    if isinstance(res, Exception):
                        results.append(
                            await self._message_to_dict(msg, include_thumbnail=False)
                        )
                    else:
                        results.append(res)
            grouped = self._group_album_messages(list(reversed(results)))
        else:
            messages = [
                await self._message_to_dict(m, include_thumbnail=False)
                for m in raw_messages
            ]
            grouped = self._group_album_messages(list(reversed(messages)))

        grouped = self._hydrate_cached_thumbnails(chat_ref, grouped)
        cache_store.merge_messages(chat_ref, grouped)
        return grouped

    def list_messages(
        self,
        chat_ref,
        limit=60,
        timeout=30,
        include_thumbnails=True,
        offset_id=0,
    ):
        return self.call(
            self._list_messages(
                chat_ref=chat_ref,
                limit=limit,
                include_thumbnails=include_thumbnails,
                offset_id=offset_id,
            ),
            timeout=timeout,
        )

    def list_messages_async(
        self,
        chat_ref,
        limit=60,
        include_thumbnails=True,
        offset_id=0,
    ):
        return self.submit(
            self._list_messages(
                chat_ref=chat_ref,
                limit=limit,
                include_thumbnails=include_thumbnails,
                offset_id=offset_id,
            ),
        )

    async def _list_newer_messages(
        self,
        chat_ref,
        min_id,
        limit=60,
        include_thumbnails=False,
    ):
        raw_messages = await self._collect_raw_messages(
            chat_ref,
            limit=limit,
            min_id=int(min_id or 0),
            reverse=True,
        )

        if not raw_messages:
            return []

        # 缓存原始消息对象供后续缩略图下载使用
        chat_key = str(chat_ref)
        for msg in raw_messages:
            self._raw_message_cache[(chat_key, int(msg.id))] = msg

        messages = [
            await self._message_to_dict(m, include_thumbnail=include_thumbnails)
            for m in raw_messages
        ]
        grouped = self._group_album_messages(messages)
        grouped = self._hydrate_cached_thumbnails(chat_ref, grouped)
        cache_store.merge_messages(chat_ref, grouped)
        return grouped

    def list_newer_messages_async(
        self,
        chat_ref,
        min_id,
        limit=60,
        include_thumbnails=False,
    ):
        return self.submit(
            self._list_newer_messages(
                chat_ref=chat_ref,
                min_id=min_id,
                limit=limit,
                include_thumbnails=include_thumbnails,
            ),
        )

    def list_messages_cached(self, chat_ref, limit=60):
        return cache_store.load_messages(chat_ref, limit=limit)

    async def _message_thumbnail_base64(self, chat_ref, message_id):
        cached = cache_store.load_thumbnail_base64(chat_ref, message_id)
        if cached:
            return cached

        # 优先使用 _list_messages() 缓存的原始消息对象，
        # 避免再次调用 get_messages() API（每条消息可节省 ~200-500ms）
        raw = self._raw_message_cache.get((str(chat_ref), int(message_id)))
        if raw is None:
            entity = await self.resolve_entity(chat_ref)
            raw = await self.client.get_messages(entity, ids=int(message_id))
            if not raw:
                return ""

        data = await self._thumbnail_bytes(raw, timeout=8)
        if not data:
            return ""

        cache_store.save_thumbnail(chat_ref, message_id, data)
        return base64.b64encode(data).decode("ascii")

    def message_thumbnail_async(self, chat_ref, message_id):
        return self.submit(
            self._message_thumbnail_base64(
                chat_ref=chat_ref,
                message_id=message_id,
            )
        )

    def _clear_cached_dialog_unread(self, chat_ref):
        dialogs = cache_store.load_dialogs()
        changed = False
        for dialog in dialogs:
            if str(dialog.get("id")) != str(chat_ref):
                continue
            if int(dialog.get("unread_count") or 0) != 0:
                dialog["unread_count"] = 0
                changed = True
            break
        if changed:
            cache_store.save_dialogs(dialogs)

    async def _mark_chat_read(self, chat_ref):
        self._clear_cached_dialog_unread(chat_ref)
        entity = await self.resolve_entity(chat_ref)
        await self.client.send_read_acknowledge(entity)
        return True

    def mark_chat_read_async(self, chat_ref):
        return self.submit(self._mark_chat_read(chat_ref))

    def purge_raw_message_cache(self, chat_ref=None):
        """清理原始消息对象缓存，释放内存。
        chat_ref=None 时清空全部缓存，否则只清指定聊天。"""
        if chat_ref is None:
            self._raw_message_cache.clear()
            return
        prefix = str(chat_ref)
        keys_to_remove = [
            k for k in self._raw_message_cache if k[0] == prefix
        ]
        for k in keys_to_remove:
            del self._raw_message_cache[k]

    async def _send_message(self, chat_ref, text):
        entity = await self.resolve_entity(chat_ref)
        message = await self.client.send_message(entity, text)
        result = await self._message_to_dict(message)
        result["chat_id"] = str(chat_ref)
        cache_store.merge_messages(chat_ref, [result])
        return result

    def send_message(self, chat_ref, text, timeout=30):
        return self.call(
            self._send_message(chat_ref=chat_ref, text=text),
            timeout=timeout,
        )

    def send_message_async(self, chat_ref, text):
        return self.submit(
            self._send_message(chat_ref=chat_ref, text=text),
        )

    async def _test_proxy(self, proxy_settings):
        client = TelegramClient(
            StringSession(),
            API_ID,
            API_HASH,
            proxy=build_telethon_proxy(proxy_settings),
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=15)
            await asyncio.wait_for(client(GetConfigRequest()), timeout=15)
            return True
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    def test_proxy_async(self, proxy_settings):
        return self.submit(self._test_proxy(proxy_settings))

    async def _ensure_connected(self):
        if self.client is None:
            self.client = self._build_client()

        if not self.client.is_connected():
            await self.client.connect()
            self._install_event_handlers()

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
        self._new_message_handler = None
        self._install_event_handlers()

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
        self._new_message_handler = None
        self._install_event_handlers()

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

    def stop(self, timeout=15):
        loop = self.loop
        if loop is None:
            self._started = False
            return

        if not loop.is_closed():
            if loop.is_running():
                try:
                    self.submit(self._stop()).result(timeout=timeout)
                except Exception:
                    pass
                try:
                    loop.call_soon_threadsafe(loop.stop)
                except RuntimeError:
                    pass
            else:
                try:
                    loop.run_until_complete(self._stop())
                except RuntimeError:
                    pass

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)

        self._started = False

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

            # 取消所有剩余任务（缩略图下载等），防止 GeneratorExit 警告
            current = asyncio.current_task()
            remaining = [t for t in asyncio.all_tasks(self.loop) if t is not current]
            for task in remaining:
                task.cancel()
            if remaining:
                await asyncio.gather(*remaining, return_exceptions=True)
        except Exception:
            pass

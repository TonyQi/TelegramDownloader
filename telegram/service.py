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

    def _install_event_handlers(self):
        if self.client is None or self._new_message_handler is not None:
            return

        async def handle_new_message(event):
            try:
                chat = await event.get_chat()
                message = await self._message_to_dict(event.message)
                message["chat_id"] = str(utils.get_peer_id(chat))
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

    async def _thumbnail_base64(self, message, timeout=3):
        if not (getattr(message, "photo", None) or getattr(message, "document", None)):
            return ""

        try:
            data = await asyncio.wait_for(
                self.client.download_media(message, file=bytes, thumb=-1),
                timeout=timeout,
            )
        except (asyncio.TimeoutError, Exception):
            return ""

        if not data:
            return ""

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
        async for dialog in self.client.iter_dialogs(limit=limit):
            key = self._cache_entity(dialog.entity)
            dialogs.append(
                {
                    "id": key,
                    "title": dialog.name or "Untitled",
                    "unread_count": int(dialog.unread_count or 0),
                    "pinned": bool(dialog.pinned),
                }
            )
        return dialogs

    def list_dialogs(self, limit=80, timeout=30):
        return self.call(self._list_dialogs(limit=limit), timeout=timeout)

    def list_dialogs_async(self, limit=80):
        return self.submit(self._list_dialogs(limit=limit))

    async def _list_messages(
        self,
        chat_ref,
        limit=60,
        include_thumbnails=True,
        offset_id=0,
    ):
        entity = await self.resolve_entity(chat_ref)
        messages = []
        async for message in self.client.iter_messages(
            entity,
            limit=limit,
            offset_id=int(offset_id or 0),
        ):
            messages.append(
                await self._message_to_dict(
                    message,
                    include_thumbnail=include_thumbnails,
                )
            )
        return self._group_album_messages(list(reversed(messages)))

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

    async def _message_thumbnail_base64(self, chat_ref, message_id):
        entity = await self.resolve_entity(chat_ref)
        message = await self.client.get_messages(entity, ids=int(message_id))
        if not message:
            return ""
        return await self._thumbnail_base64(message, timeout=8)

    def message_thumbnail_async(self, chat_ref, message_id):
        return self.submit(
            self._message_thumbnail_base64(
                chat_ref=chat_ref,
                message_id=message_id,
            )
        )

    async def _send_message(self, chat_ref, text):
        entity = await self.resolve_entity(chat_ref)
        message = await self.client.send_message(entity, text)
        result = await self._message_to_dict(message)
        result["chat_id"] = str(chat_ref)
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

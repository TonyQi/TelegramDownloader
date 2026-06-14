import base64
import json
import re
from pathlib import Path

from config import CACHE_DIR


class CacheStore:
    def __init__(self, root: Path = CACHE_DIR):
        self.root = root
        self.dialogs_file = self.root / "dialogs.json"
        self.messages_dir = self.root / "messages"
        self.thumbnails_dir = self.root / "thumbnails"
        self.avatars_dir = self.root / "avatars"
        self.positions_file = self.root / "positions.json"

    @staticmethod
    def _safe_key(value) -> str:
        key = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "unknown")).strip("._")
        return key or "unknown"

    @staticmethod
    def _read_json(path: Path, fallback):
        try:
            if not path.exists():
                return fallback
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return fallback

    @staticmethod
    def _write_json(path: Path, data):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            tmp_path.replace(path)
        except Exception:
            pass

    @staticmethod
    def _read_bytes_base64(path: Path) -> str:
        try:
            if not path.exists():
                return ""
            return base64.b64encode(path.read_bytes()).decode("ascii")
        except Exception:
            return ""

    @staticmethod
    def _write_bytes(path: Path, data: bytes):
        if not data:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            tmp_path.write_bytes(data)
            tmp_path.replace(path)
        except Exception:
            pass

    def load_dialogs(self):
        data = self._read_json(self.dialogs_file, [])
        return data if isinstance(data, list) else []

    def save_dialogs(self, dialogs):
        if isinstance(dialogs, list):
            self._write_json(self.dialogs_file, dialogs)

    def _messages_file(self, chat_ref) -> Path:
        return self.messages_dir / f"{self._safe_key(chat_ref)}.json"

    def load_messages(self, chat_ref, limit=60):
        messages = self._read_json(self._messages_file(chat_ref), [])
        if not isinstance(messages, list):
            return []
        try:
            messages = sorted(messages, key=lambda item: int(item.get("id", 0)))
        except Exception:
            pass
        if limit:
            return messages[-int(limit):]
        return messages

    def merge_messages(self, chat_ref, messages, max_items=500):
        if not isinstance(messages, list):
            return

        current = self.load_messages(chat_ref, limit=0)
        merged = {}
        for message in current + messages:
            if not isinstance(message, dict):
                continue
            message_id = message.get("id")
            if message_id is None:
                continue
            merged[str(message_id)] = message

        try:
            ordered = sorted(merged.values(), key=lambda item: int(item.get("id", 0)))
        except Exception:
            ordered = list(merged.values())

        if max_items and len(ordered) > max_items:
            ordered = ordered[-int(max_items):]
        self._write_json(self._messages_file(chat_ref), ordered)

    def load_thumbnail_base64(self, chat_ref, message_id) -> str:
        path = (
            self.thumbnails_dir
            / self._safe_key(chat_ref)
            / f"{self._safe_key(message_id)}.bin"
        )
        return self._read_bytes_base64(path)

    def save_thumbnail(self, chat_ref, message_id, data: bytes):
        path = (
            self.thumbnails_dir
            / self._safe_key(chat_ref)
            / f"{self._safe_key(message_id)}.bin"
        )
        self._write_bytes(path, data)

    def load_avatar_base64(self, dialog_id) -> str:
        return self._read_bytes_base64(
            self.avatars_dir / f"{self._safe_key(dialog_id)}.bin"
        )

    def save_avatar(self, dialog_id, data: bytes):
        self._write_bytes(self.avatars_dir / f"{self._safe_key(dialog_id)}.bin", data)

    def load_chat_position(self, chat_ref):
        positions = self._read_json(self.positions_file, {})
        if not isinstance(positions, dict):
            return {}
        position = positions.get(self._safe_key(chat_ref), {})
        return position if isinstance(position, dict) else {}

    def save_chat_position(self, chat_ref, position):
        if not isinstance(position, dict):
            return
        positions = self._read_json(self.positions_file, {})
        if not isinstance(positions, dict):
            positions = {}
        positions[self._safe_key(chat_ref)] = position
        self._write_json(self.positions_file, positions)


cache_store = CacheStore()

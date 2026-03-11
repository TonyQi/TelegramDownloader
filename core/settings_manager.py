import json
from pathlib import Path
from threading import RLock

from config import DATA_DIR, DEFAULT_SETTINGS, SETTINGS_FILE


class SettingsManager:
    def __init__(self):
        self._lock = RLock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._data = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        with self._lock:
            if SETTINGS_FILE.exists():
                try:
                    loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        self._data.update(loaded)
                except Exception:
                    pass
            self.save()

    def save(self):
        with self._lock:
            SETTINGS_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            self.save()

    def all(self):
        with self._lock:
            return dict(self._data)

    def ensure_download_dir(self) -> Path:
        path = Path(self.get("download_dir"))
        path.mkdir(parents=True, exist_ok=True)
        return path


settings_manager = SettingsManager()

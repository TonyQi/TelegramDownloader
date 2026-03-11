from pathlib import Path

APP_NAME = "Telegram Desktop Downloader"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = BASE_DIR / "sessions"
DOWNLOAD_DIR = BASE_DIR / "downloads"

SETTINGS_FILE = DATA_DIR / "settings.json"
DB_FILE = DATA_DIR / "data" / "tasks.sqlite3"
SESSION_FILE = SESSIONS_DIR / "telegram"

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

CHUNK_SIZE = 512 * 1024

GLOBAL_PROXY = {
    "scheme": "socks5",   # socks5 / http
    "host": "127.0.0.1",
    "port": 7897,
    "username": "",
    "password": ""
}

DEFAULT_SETTINGS = {
    "download_dir": str(DOWNLOAD_DIR),
    "max_concurrent_tasks": 3,
    "chunk_concurrency": 4,
    "refresh_interval_ms": 700
}

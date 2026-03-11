import json
from pathlib import Path


def meta_path(file_path: str) -> Path:
    path = Path(file_path)
    return path.with_suffix(path.suffix + ".meta.json")


def load_meta(file_path: str) -> dict:
    path = meta_path(file_path)
    if not path.exists():
        return {"downloaded_chunks": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"downloaded_chunks": []}


def save_meta(file_path: str, data: dict):
    path = meta_path(file_path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_meta(file_path: str):
    path = meta_path(file_path)
    if path.exists():
        path.unlink()

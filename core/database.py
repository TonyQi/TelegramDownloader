import sqlite3
from threading import RLock
from pathlib import Path

from config import DATA_DIR, DB_FILE
from models.task import DownloadTask


class Database:
    def __init__(self):
        Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock:
            self.conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    name TEXT,
                    status TEXT NOT NULL,
                    total_size INTEGER NOT NULL DEFAULT 0,
                    downloaded_size INTEGER NOT NULL DEFAULT 0,
                    speed REAL NOT NULL DEFAULT 0,
                    progress REAL NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            self.conn.commit()

    def upsert_task(self, task):
        with self._lock:
            self.conn.execute(
                '''
                INSERT INTO tasks (
                    task_id, url, name, status, total_size, downloaded_size,
                    speed, progress, error, file_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    url=excluded.url,
                    name=excluded.name,
                    status=excluded.status,
                    total_size=excluded.total_size,
                    downloaded_size=excluded.downloaded_size,
                    speed=excluded.speed,
                    progress=excluded.progress,
                    error=excluded.error,
                    file_path=excluded.file_path,
                    updated_at=excluded.updated_at
                ''',
                (
                    task.task_id,
                    task.url,
                    task.name,
                    task.status,
                    task.total_size,
                    task.downloaded_size,
                    task.speed,
                    task.progress,
                    task.error,
                    task.file_path,
                    task.created_at,
                    task.updated_at,
                ),
            )
            self.conn.commit()

    def list_tasks(self):
        with self._lock:
            rows = self.conn.execute(
                '''
                SELECT
                    task_id, url, name, status, total_size, downloaded_size,
                    speed, progress, error, file_path, created_at, updated_at
                FROM tasks
                ORDER BY updated_at DESC, created_at DESC
                '''
            ).fetchall()

        tasks = []
        for row in rows:
            task = DownloadTask(
                task_id=row["task_id"],
                url=row["url"],
            )
            task.name = row["name"] or ""
            task.status = row["status"]
            task.total_size = int(row["total_size"] or 0)
            task.downloaded_size = int(row["downloaded_size"] or 0)
            task.speed = float(row["speed"] or 0)
            task.progress = float(row["progress"] or 0)
            task.error = row["error"] or ""
            task.file_path = row["file_path"] or ""
            task.created_at = row["created_at"]
            task.updated_at = row["updated_at"]
            if (
                task.total_size > 0
                and task.file_path
                and Path(task.file_path).exists()
                and Path(task.file_path).stat().st_size >= task.total_size
            ):
                task.downloaded_size = task.total_size
                task.progress = 100.0
                task.speed = 0.0
                task.status = "finished"
            tasks.append(task)

        return tasks

    def delete_task(self, task_id: str):
        with self._lock:
            self.conn.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
            self.conn.commit()

    def close(self):
        with self._lock:
            self.conn.close()


db = Database()

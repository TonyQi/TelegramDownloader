from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, RLock


@dataclass
class DownloadTask:
    task_id: str
    url: str
    status: str = "queued"
    name: str = ""
    total_size: int = 0
    downloaded_size: int = 0
    speed: float = 0.0
    progress: float = 0.0
    error: str = ""
    file_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    pause_event: Event = field(default_factory=Event, repr=False)
    cancel_event: Event = field(default_factory=Event, repr=False)
    state_lock: RLock = field(default_factory=RLock, repr=False)

    def touch(self):
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def set_status(self, status: str):
        with self.state_lock:
            self.status = status
            self.touch()

    def set_error(self, error: str):
        with self.state_lock:
            self.error = error
            self.touch()

    def update_progress(self, downloaded_size: int, total_size: int, speed: float):
        with self.state_lock:
            self.downloaded_size = downloaded_size
            self.total_size = total_size
            self.speed = speed
            self.progress = (downloaded_size / total_size * 100.0) if total_size else 0.0
            self.touch()

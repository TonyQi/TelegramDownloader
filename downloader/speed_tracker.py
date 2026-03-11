import time
from collections import deque


class SpeedTracker:
    def __init__(self, window_seconds: float = 5.0):
        self.window_seconds = window_seconds
        self.samples = deque()

    def add(self, size: int):
        now = time.time()
        self.samples.append((now, size))
        self._cleanup(now)

    def _cleanup(self, now: float):
        while self.samples and now - self.samples[0][0] > self.window_seconds:
            self.samples.popleft()

    def get_speed(self) -> float:
        now = time.time()
        self._cleanup(now)
        total = sum(size for _, size in self.samples)
        if not self.samples:
            return 0.0
        elapsed = max(now - self.samples[0][0], 0.001)
        return total / elapsed

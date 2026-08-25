import time
import threading
from collections import deque


class RateMonitor:
    def __init__(self, window_seconds=60):
        self._lock = threading.Lock()
        self._timestamps = deque()
        self._window = window_seconds

    def record(self):
        now = time.time()
        with self._lock:
            self._timestamps.append(now)
            while self._timestamps and self._timestamps[0] < now - self._window:
                self._timestamps.popleft()

    @property
    def rate(self):
        now = time.time()
        with self._lock:
            while self._timestamps and self._timestamps[0] < now - self._window:
                self._timestamps.popleft()
            return len(self._timestamps)
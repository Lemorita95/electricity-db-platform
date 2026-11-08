import time
import threading
import cdsapi

from managers.config import CDS_API_URL, CDS_API_KEY
from managers.rate_monitor import RateMonitor

REQUESTS_PER_SECOND = 2
MAX_CONNECTIONS = 2
REQUEST_TIMEOUT = 300
MAX_RETRIES = 3
INITIAL_BACKOFF = 60


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return '429' in msg or 'too many requests' in msg or 'queued requests' in msg


class CopernicusClient:
    '''
    - jobs are submitted one at a time, at most REQUESTS_PER_SECOND
    - a job holds its slot until CDS has finished it, so at most MAX_CONNECTIONS are open at once
    - one client per process (managers.shared), so the limits hold across sync workers
    - 429 and a full CDS queue retry at 60 s -> 120 s -> 240 s, waiting outside the slot; other errors raise
    '''
    def __init__(self, status_callback=None):
        self._status_callback = status_callback or (lambda msg: None)
        self._lock = threading.Lock()
        self._last_request_time = 0
        self._conn_semaphore = threading.Semaphore(MAX_CONNECTIONS)
        self.monitor = RateMonitor(window_seconds=60)

        self._client = cdsapi.Client(
            url=CDS_API_URL or None, key=CDS_API_KEY, quiet=True, progress=False, timeout=REQUEST_TIMEOUT
        )
        self._status_callback("[copernicus] client initialized")

    def _throttle(self):
        with self._lock:
            elapsed = time.time() - self._last_request_time
            min_interval = 1 / REQUESTS_PER_SECOND
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()

    def retrieve(self, dataset: str, request: dict) -> 'cdsapi.Results':
        for attempt in range(MAX_RETRIES):
            try:
                with self._conn_semaphore:
                    self._throttle()
                    self.monitor.record()
                    self._status_callback(f"[copernicus] retrieving dataset={dataset}")
                    result = self._client.retrieve(dataset, request)  # returns once the job has finished
                    self._status_callback("[copernicus] retrieved successfully")
                    return result
            except Exception as exc:
                if not _is_retryable(exc):
                    raise
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                self._status_callback(f"[copernicus] {exc}; retry {attempt + 1}/{MAX_RETRIES} in {backoff}s")
                time.sleep(backoff)

        raise Exception(f"retrieve failed after {MAX_RETRIES} retries")

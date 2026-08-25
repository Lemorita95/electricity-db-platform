import time
import threading
import cdsapi

from managers.config import CDS_API_URL, CDS_API_KEY
from managers.rate_monitor import RateMonitor

REQUESTS_PER_SECOND = 2
MAX_CONNECTIONS = 5
REQUEST_TIMEOUT = 300
MAX_RETRIES = 3
INITIAL_BACKOFF = 60


class CopernicusClient:
    def __init__(self, status_callback=None):
        self._status_callback = status_callback or (lambda msg: None)
        self._lock = threading.Lock()
        self._last_request_time = 0
        self._conn_semaphore = threading.Semaphore(MAX_CONNECTIONS)
        self.monitor = RateMonitor(window_seconds=60)

        self._client = cdsapi.Client(url=CDS_API_URL or None, key=CDS_API_KEY, quiet=True, progress=False)
        self._status_callback("[copernicus] client initialized")
        self._start_watchdog()

    def _throttle(self):
        with self._lock:
            elapsed = time.time() - self._last_request_time
            min_interval = 1 / REQUESTS_PER_SECOND
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()

    def _start_watchdog(self, interval=10):
        def _watch():
            while True:
                time.sleep(interval)
                rate = self.monitor.rate
                self._status_callback(f"[copernicus] {rate} req/60s — {rate / 60:.1f} req/s")
        threading.Thread(target=_watch, daemon=True).start()

    def retrieve(self, dataset: str, request: dict) -> 'cdsapi.Results':
        for attempt in range(MAX_RETRIES):
            with self._lock:
                elapsed = time.time() - self._last_request_time
                min_interval = 1 / REQUESTS_PER_SECOND
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                self._last_request_time = time.time()

            self.monitor.record()
            try:
                with self._conn_semaphore:
                    self._status_callback(f"[copernicus] retrieving dataset={dataset}")
                    result = self._client.retrieve(dataset, request)
                    self._status_callback(f"[copernicus] retrieved successfully")
                    return result
            except Exception as exc:
                msg = str(exc).lower()
                if '429' in msg or 'too many' in msg or 'rate' in msg:
                    backoff = INITIAL_BACKOFF * (2 ** attempt)
                    self._status_callback(
                        f"[copernicus] rate limited, retry {attempt + 1}/{MAX_RETRIES} in {backoff}s"
                    )
                    time.sleep(backoff)
                    continue
                raise

        raise Exception(f"retrieve failed after {MAX_RETRIES} retries")
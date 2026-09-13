import time
import threading
import xml.etree.ElementTree as ET
import requests

from managers.config import ENTSOE_BASE_URL, ENTSOE_API_KEY
from managers.rate_monitor import RateMonitor


REQUESTS_PER_SECOND = 6
REQUEST_TIMEOUT = 300
BAN_WAIT_SECONDS = 600


class EntsoClient:
    '''
    - a bad request (e.g. end before start) raises a 400 code
    - a good request but empty data (e.g. data too far in future) 
        raises a 200 code but with a `Acknowledgement_MarketDocument` type
    '''
    def __init__(self, status_callback=None):
        self.session = requests.Session()
        self.base_url = ENTSOE_BASE_URL
        self.session.params = {'securityToken': ENTSOE_API_KEY}
        self._last_request_time = 0
        self._lock = threading.Lock()
        self.monitor = RateMonitor(window_seconds=60)
        self._status_callback = status_callback or (lambda msg: None)
        self._start_watchdog()

    def _start_watchdog(self, interval=10):
        def _watch():
            while True:
                time.sleep(interval)
                rate = self.monitor.rate
                self._status_callback(f"{rate} req/60s — {rate / 60:.1f} req/s")
        threading.Thread(target=_watch, daemon=True).start()

    def _throttle(self):
        with self._lock:
            elapsed = time.time() - self._last_request_time
            min_interval = 1 / REQUESTS_PER_SECOND
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()

    def get(self, params: dict, retries: int = 3) -> ET.Element:
        self._throttle()
        self.monitor.record()
        for attempt in range(retries):
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 429:
                self._status_callback(f"[monitor] rate limited, waiting {BAN_WAIT_SECONDS // 60} minutes...")
                time.sleep(BAN_WAIT_SECONDS)
                continue
            response.raise_for_status()
            return ET.fromstring(response.content)
        raise Exception(f"failed after {retries} attempts")
import time
import threading
import xml.etree.ElementTree as ET
import requests

from managers.config import ENTSOE_BASE_URL, ENTSOE_API_KEY
from managers.rate_monitor import RateMonitor


REQUESTS_PER_SECOND = 6
REQUEST_TIMEOUT = 300
BAN_WAIT_SECONDS = 600
RETRY_WAITS = [10, 20, 40]


def _redact(text: str) -> str:
    '''the token travels as a URL parameter, and requests puts the URL in its error messages'''
    return text.replace(ENTSOE_API_KEY, '***') if ENTSOE_API_KEY else text


class EntsoClient:
    '''
    - a bad request (e.g. end before start) raises a 400 code, never retried
    - a good request but empty data (e.g. data too far in future)
        raises a 200 code but with a `Acknowledgement_MarketDocument` type
    - 5xx (including ENTSO-E's 527/599) and connection errors retry at 10 s -> 20 s -> 40 s
    - error messages never carry the security token
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

    def get(self, params: dict) -> ET.Element:
        last_error = None
        for wait in RETRY_WAITS + [None]:
            self._throttle()
            self.monitor.record()
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
            except requests.RequestException as e:
                last_error = f"{type(e).__name__}: {_redact(str(e))}"
            else:
                if response.status_code < 400:
                    return ET.fromstring(response.content)

                url = _redact(response.url)
                if response.status_code == 429:
                    self._status_callback(f"[monitor] rate limited, waiting {BAN_WAIT_SECONDS // 60} minutes...")
                    last_error = f"429 rate limited for {url}"
                    if wait is not None:
                        wait = BAN_WAIT_SECONDS
                elif response.status_code >= 500:
                    last_error = f"{response.status_code} Server Error for {url}"
                else:
                    raise requests.HTTPError(f"{response.status_code} Client Error for {url}", response=response) from None

            if wait is None:
                break
            self._status_callback(f"[monitor] {last_error}, retrying in {wait} s")
            time.sleep(wait)

        raise Exception(f"failed after {len(RETRY_WAITS)} retries: {last_error}")
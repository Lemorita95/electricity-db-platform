import time
import threading
import requests

from managers.config import JAO_NORDIC_BASE_URL
from managers.rate_monitor import RateMonitor


REQUESTS_PER_SECOND = 1
REQUEST_TIMEOUT = 300
RETRY_WAITS = [10, 20, 40]


class JaoRejected(Exception):
    '''JAO refused the request but answered HTTP 200 with rejected: true'''


class JaoClient:
    '''
    follows JAO's Publication Tool API guide:
    - requests are strictly sequential, at most 1/s (limit is 100/min)
    - 400/404 are never retried unchanged
    - 429 waits Retry-After; 5xx and non-JSON bodies retry at 10 s -> 20 s -> 40 s
    - a 200 can still be a refusal, so `rejected` is checked
    '''
    def __init__(self, status_callback=None):
        self.session = requests.Session()
        self.session.headers.update({'Accept-Encoding': 'gzip'})
        self.base_url = JAO_NORDIC_BASE_URL
        self._last_request_time = 0
        self._lock = threading.Lock()
        self.monitor = RateMonitor(window_seconds=60)
        self._status_callback = status_callback or (lambda msg: None)

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        min_interval = 1 / REQUESTS_PER_SECOND
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, path: str, params: dict):
        url = f"{self.base_url}/{path}"
        with self._lock:
            last_error = None
            for wait in RETRY_WAITS + [None]:
                self._throttle()
                self.monitor.record()
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)

                if response.status_code in (400, 404):
                    raise requests.HTTPError(
                        f"JAO {response.status_code} for {path}: {response.text[:300]}", response=response
                    )

                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', '')
                    if wait is not None and retry_after.isdigit():
                        wait = int(retry_after)
                    last_error = "429 rate limited"
                elif response.status_code >= 500:
                    last_error = f"{response.status_code}: {response.text[:300]}"
                else:
                    response.raise_for_status()
                    try:
                        body = response.json()
                    except ValueError:
                        last_error = f"non-JSON body: {response.text[:300]}"
                    else:
                        if isinstance(body, dict) and body.get('rejected'):
                            raise JaoRejected(body.get('messages'))
                        return body

                if wait is None:
                    break
                self._status_callback(f"[jao] {last_error}, retrying in {wait} s")
                time.sleep(wait)

        raise Exception(f"JAO {path} failed after {len(RETRY_WAITS)} retries: {last_error}")

    def get(self, dataset: str, params: dict) -> dict:
        return self._request(f"data/{dataset}", params)

    def monitoring(self, from_utc: str, to_utc: str) -> dict:
        return self._request("system/monitoring", {'FromUtc': from_utc, 'ToUtc': to_utc})

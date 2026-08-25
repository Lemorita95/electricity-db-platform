import time
import threading
import eumdac

from managers.config import EUMDAC_CONSUMER_KEY, EUMDAC_CONSUMER_SECRET
from managers.rate_monitor import RateMonitor

REQUESTS_PER_SECOND = 40
MAX_CONNECTIONS = 15
REQUEST_TIMEOUT = 300
TOKEN_REFRESH_SLACK = 60   # refresh token this many seconds before expiry


class EumetClient:
    def __init__(self, status_callback=None):
        self._status_callback = status_callback or (lambda msg: None)
        self._lock = threading.Lock()
        self._last_request_time = 0
        self._conn_semaphore = threading.Semaphore(MAX_CONNECTIONS)
        self.monitor = RateMonitor(window_seconds=60)

        self._token = self._init_token()
        self.datastore = eumdac.DataStore(self._token)

        self._start_watchdog()

    # ------------------------------------------------------------------
    # auth
    # ------------------------------------------------------------------

    def _init_token(self) -> eumdac.AccessToken:
        if not EUMDAC_CONSUMER_KEY or not EUMDAC_CONSUMER_SECRET:
            raise EnvironmentError(
                "EUMDAC_CONSUMER_KEY and EUMDAC_CONSUMER_SECRET must be set"
            )
        credentials = (EUMDAC_CONSUMER_KEY, EUMDAC_CONSUMER_SECRET)
        token = eumdac.AccessToken(credentials)
        self._status_callback(f"[eumet] token acquired, expires {token.expiration}")
        return token

    def _refresh_token_if_needed(self):
        expiry = self._token.expiration.timestamp()
        if time.time() >= expiry - TOKEN_REFRESH_SLACK:
            self._token = self._init_token()
            self.datastore = eumdac.DataStore(self._token)
            self._status_callback("[eumet] token refreshed")

    # ------------------------------------------------------------------
    # rate control
    # ------------------------------------------------------------------

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
                self._status_callback(f"[eumet] {rate} req/60s — {rate / 60:.1f} req/s")
        threading.Thread(target=_watch, daemon=True).start()

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    def get_collection(self, collection_id: str) -> eumdac.collection.Collection:
        self._throttle()
        self._refresh_token_if_needed()
        self.monitor.record()
        with self._conn_semaphore:
            return self.datastore.get_collection(collection_id)
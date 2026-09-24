"""
managers/__init__.py builds one client per source at import time, and two
of them (Copernicus, EUMETSAT) make a real network call in their
constructor. So importing anything under `managers` needs cdsapi and
eumdac stubbed out first, or it hangs / fails without credentials.

Each patch below returns a NEW MagicMock every call (not a shared one),
so tests that build their own client instance don't leak state into
each other.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

for var, default in [
    ("ENTSOE_API_KEY", "test-key"),
    ("ENTSOE_BASE_URL", "https://web-api.tp.entsoe.eu/api"),
    ("CDS_API_URL", "https://cds.climate.copernicus.eu/api"),
    ("CDS_API_KEY", "test-key"),
    ("EUMDAC_CONSUMER_KEY", "test-key"),
    ("EUMDAC_CONSUMER_SECRET", "test-secret"),
]:
    os.environ.setdefault(var, default)

import cdsapi
import eumdac


def _fresh_token(*args, **kwargs):
    token = mock.MagicMock()
    token.expiration = datetime.now(timezone.utc) + timedelta(days=1)
    return token


mock.patch.object(cdsapi, "Client", side_effect=lambda *a, **k: mock.MagicMock()).start()
mock.patch.object(eumdac, "AccessToken", side_effect=_fresh_token).start()
mock.patch.object(eumdac, "DataStore", side_effect=lambda *a, **k: mock.MagicMock()).start()

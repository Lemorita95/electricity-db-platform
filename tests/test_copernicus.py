"""
Basic tests for src/managers/copernicus/* — normal case only. No network.
"""
import csv
import io
import zipfile
from datetime import datetime
from unittest import mock

import pytest

from managers.copernicus.copernicus_client import CopernicusClient
from managers.copernicus import copernicus_endpoints as ce
from managers.copernicus import copernicus_parser as cp
from managers.config import NORDICS_CODES, QUERY_CONFIGS


class _FakeCdsResults:
    """Stands in for cdsapi.Results: parse_weather only calls .download(path)."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def download(self, path):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["valid_time", "fdir", "ssrd", "t2m", "u10", "v10"])
        writer.writeheader()
        writer.writerows(self._rows)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("data.csv", buf.getvalue())


def test_parse_weather_maps_a_csv_row_to_a_record():
    results = _FakeCdsResults([{
        "valid_time": "2025-06-10T00:00:00Z", "fdir": "120.5", "ssrd": "300.2",
        "t2m": "285.1", "u10": "2.3", "v10": "-1.1",
    }])
    records = cp.parse_weather(results, "SE3")
    assert len(records) == 1
    assert records[0].zone == "SE3"
    assert records[0].fdir == 120.5


def test_parse_weather_skips_a_blank_valid_time():
    # regression: a present-but-empty valid_time column used to reach
    # datetime.fromisoformat('') and raise, instead of being skipped.
    results = _FakeCdsResults([
        {"valid_time": "", "fdir": "1.0", "ssrd": "2.0", "t2m": "3.0", "u10": "4.0", "v10": "5.0"},
        {"valid_time": "2025-06-10T00:00:00Z", "fdir": "1.0", "ssrd": "2.0",
         "t2m": "3.0", "u10": "4.0", "v10": "5.0"},
    ])
    records = cp.parse_weather(results, "SE3")
    assert len(records) == 1


def test_get_era5_builds_expected_request():
    captured = {}

    def fake_retrieve(dataset, request):
        captured["dataset"] = dataset
        captured["request"] = request
        return mock.Mock()

    with mock.patch.object(ce.copernicus_client, "retrieve", side_effect=fake_retrieve), \
         mock.patch.object(ce, "parse_weather", return_value=[]):
        ce.get_era5("SE3", datetime(2025, 6, 1), datetime(2025, 6, 2))

    assert captured["dataset"] == QUERY_CONFIGS["copernicus"]["dataset"]
    assert captured["request"]["location"]["latitude"] == NORDICS_CODES["SE3"]["lat"]


def test_client_retrieve_returns_cdsapi_result():
    client = CopernicusClient()
    sentinel = mock.Mock()
    client._client.retrieve.return_value = sentinel
    assert client.retrieve("dataset", {}) is sentinel


def test_client_retrieve_raises_on_non_retryable_error():
    client = CopernicusClient()
    client._client.retrieve.side_effect = ValueError("malformed request")
    with pytest.raises(ValueError):
        client.retrieve("dataset", {})

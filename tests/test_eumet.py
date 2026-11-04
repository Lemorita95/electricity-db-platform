"""
Basic tests for src/managers/eumet/* — normal case only. No network.
"""
import io
import zipfile
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np
import pytest
import xarray as xr

from managers.eumet import eumet_client as ec
from managers.eumet.eumet_client import EumetClient
from managers.eumet import eumet_endpoints as ee
from managers.eumet import eumet_parser as ep
from managers.config import QUERY_CONFIGS


def test_get_sarah3_searches_each_configured_var_type():
    fake_collection = mock.Mock()
    fake_collection.search.return_value = []

    fake_client = mock.Mock(get_collection=mock.Mock(return_value=fake_collection))
    with mock.patch.object(ee, "get_eumet_client", return_value=fake_client):
        list(ee.get_sarah3("SE3", datetime(2025, 6, 1), datetime(2025, 6, 2)))

    called_var_types = {c.kwargs["type"] for c in fake_collection.search.call_args_list}
    assert called_var_types == set(QUERY_CONFIGS["eumet"]["var_type"])


@pytest.fixture
def fake_eumdac(monkeypatch):
    monkeypatch.setattr(ec, "EUMDAC_CONSUMER_KEY", "test-key")
    monkeypatch.setattr(ec, "EUMDAC_CONSUMER_SECRET", "test-secret")
    token = mock.Mock(expiration=datetime.now(timezone.utc) + timedelta(days=1))
    with mock.patch.object(ec.eumdac, "AccessToken", return_value=token) as access_token, \
         mock.patch.object(ec.eumdac, "DataStore") as datastore:
        yield access_token, datastore


def test_client_get_collection_delegates_to_datastore(fake_eumdac):
    access_token, datastore = fake_eumdac
    client = EumetClient()
    access_token.assert_not_called()  # no token until the first request

    sentinel = mock.Mock()
    datastore.return_value.get_collection.return_value = sentinel
    assert client.get_collection("EO:EUM:DAT:0863") is sentinel
    access_token.assert_called_once()


def test_client_without_credentials_fails_on_first_request(monkeypatch):
    monkeypatch.setattr(ec, "EUMDAC_CONSUMER_KEY", None)
    monkeypatch.setattr(ec, "EUMDAC_CONSUMER_SECRET", None)
    client = EumetClient()  # building it needs no credentials
    with pytest.raises(EnvironmentError, match="EUMDAC_CONSUMER_KEY"):
        client.get_collection("EO:EUM:DAT:0863")


def test_parse_irradiance_extracts_the_requested_variable(tmp_path):
    # a tiny real lat/lon/time grid, zipped -- the same shape EUMETSAT ships.
    # SE3 = lat 59.33, lon 18.07 -> nearest grid point below is (59.5, 18.0).
    sis = np.zeros((1, 3, 3))
    sis[0, 1, 1] = 111.0
    ds = xr.Dataset(
        {"SIS": (("time", "lat", "lon"), sis)},
        coords={
            "time": np.array(["2025-06-10T00:00:00"], dtype="datetime64[ns]"),
            "lat": [59.0, 59.5, 60.0],
            "lon": [17.5, 18.0, 18.5],
        },
    )
    nc_path = tmp_path / "product.nc"
    ds.to_netcdf(nc_path, engine="netcdf4")
    zip_path = tmp_path / "product.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(nc_path, arcname="data.nc")

    product = mock.Mock()
    product.open.return_value = io.BytesIO(zip_path.read_bytes())

    records = ep.parse_irradiance(product, "SE3", "SIS")

    assert len(records) == 1
    assert records[0].sis == 111.0
    assert records[0].sid is None

"""
Basic tests for src/managers/jao/* — confirms the normal case works for the
parser, the hourly endpoint and the client, not every edge case. No network calls.
"""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
import requests
import sqlalchemy as sa

from managers.config import QUERY_CONFIGS
from managers.jao import jao_client as jc
from managers.jao import jao_endpoints as je
from managers.jao import jao_parser as jp
from master.db.models import BindingCnec, CnecPtdf

FIXTURE = Path(__file__).parent / "fixtures" / "jao_fb_shadow_price_sample.json"
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "91fa2b2f548a_add_binding_cnec_and_cnec_ptdf.py"

T1100 = datetime(2026, 3, 10, 11, 0, tzinfo=timezone.utc)

# day-ahead prices for 2026-03-10 11:00
PRICES_1100 = {
    "DK1": 110.19, "DK2": 96.48, "FI": 41.14, "NO1": 112.42, "NO2": 112.94, "NO3": 73.03,
    "NO4": 26.89, "NO5": 109.95, "SE1": 32.88, "SE2": 26.73, "SE3": 64.78, "SE4": 82.59,
}


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


def _response(status=200, body=None, text=""):
    resp = mock.Mock(spec=requests.Response, status_code=status, text=text, headers={})
    resp.json.return_value = body
    resp.raise_for_status.return_value = None
    return resp


def test_parse_binding_cnecs_maps_fields_and_ptdfs(payload):
    records = jp.parse_binding_cnecs(payload["data"], "NORDIC")
    assert len(records) == 14
    assert {r.resolution for r in records} == {"PT15M"}

    first = records[0]
    assert (first.zone, first.timestamp, first.cnec_name) == ("NORDIC", T1100, "FI_PTC_RAC_SE1-FI")
    assert (first.ram, first.flow_fb) == (1900.0, 1900.0)
    assert first.shadow_price == pytest.approx(8.2490321692)
    assert len(first.ptdfs) == 31  # 12 zones + 19 HVDC hubs, zeros included
    assert {p.bidding_zone: p.ptdf for p in first.ptdfs}["FI_FS"] == -1.0


def test_shadow_prices_and_ptdfs_reconstruct_zone_prices(payload):
    '''p_z = λ − Σ μ_k·PTDF_k,z; 11 zones within €0.006, DK1 is the known outlier'''
    records = [r for r in jp.parse_binding_cnecs(payload["data"], "NORDIC") if r.timestamp == T1100]

    def congestion(zone):
        return sum(r.shadow_price * {p.bidding_zone: p.ptdf for p in r.ptdfs}[zone] for r in records)

    others = [z for z in PRICES_1100 if z != "DK1"]
    lam = sum(PRICES_1100[z] + congestion(z) for z in others) / len(others)
    residual = {z: PRICES_1100[z] - (lam - congestion(z)) for z in PRICES_1100}

    assert all(abs(residual[z]) < 0.006 for z in others)
    assert residual["DK1"] == pytest.approx(13.64, abs=0.01)


def test_get_binding_cnecs_requests_one_hour_at_a_time(payload):
    calls = []

    def fake_get(dataset, params):
        calls.append(params)
        return payload

    with mock.patch.object(je.get_jao_client(), "get", side_effect=fake_get):
        batches = list(je.get_binding_cnecs(
            "NORDIC", datetime(2026, 3, 10, 10, tzinfo=timezone.utc), datetime(2026, 3, 10, 12, tzinfo=timezone.utc)
        ))

    assert len(batches) == 2
    assert [(p["FromUtc"], p["ToUtc"]) for p in calls] == [
        ("2026-03-10T10:00:00.000Z", "2026-03-10T11:00:00.000Z"),
        ("2026-03-10T11:00:00.000Z", "2026-03-10T12:00:00.000Z"),
    ]
    assert json.loads(calls[0]["Filter"]) == {"hasShadowPrice": True}
    assert "Skip" not in calls[0]


def test_get_binding_cnecs_stops_at_a_day_not_yet_received(payload):
    file_type = QUERY_CONFIGS["jao_binding_cnec"]["monitoring_file_type"]

    def fake_monitoring(from_utc, to_utc):
        # business day 3 Nov starts at 2 Nov 23:00Z
        status = "Received" if from_utc == "2026-11-02T23:00:00.000Z" else "Expected"
        return {"data": [{"fileType": "PRE", "status": "Received"}, {"fileType": file_type, "status": status}],
                "rejected": False}

    messages = []
    with mock.patch.object(je, "_utc_now", return_value=datetime(2026, 11, 4, 12, tzinfo=timezone.utc)), \
         mock.patch.object(je.get_jao_client(), "get", return_value=payload), \
         mock.patch.object(je.get_jao_client(), "monitoring", side_effect=fake_monitoring):
        batches = list(je.get_binding_cnecs(
            "NORDIC", datetime(2026, 11, 3, 22, tzinfo=timezone.utc), datetime(2026, 11, 4, 2, tzinfo=timezone.utc),
            progress_callback=messages.append,
        ))

    assert len(batches) == 1
    assert messages[-1] == "JAO: 2026-11-04 Expected, stopping"


def test_client_retries_5xx_then_fails():
    client = jc.JaoClient()
    with mock.patch.object(jc.time, "sleep"), \
         mock.patch.object(client.session, "get", return_value=_response(503, text="<html>IIS</html>")) as get:
        with pytest.raises(Exception, match="failed after 3 retries: 503"):
            client.get("fbDomainShadowPrice", {})
    assert get.call_count == 4


def test_client_does_not_retry_404():
    client = jc.JaoClient()
    with mock.patch.object(client.session, "get", return_value=_response(404, text="not found")) as get:
        with pytest.raises(requests.HTTPError):
            client.get("fbDomainShadowPrice", {})
    assert get.call_count == 1


def test_client_raises_on_rejected_200():
    client = jc.JaoClient()
    body = {"rejected": True, "messages": ["range too large"], "data": []}
    with mock.patch.object(client.session, "get", return_value=_response(body=body)):
        with pytest.raises(jc.JaoRejected, match="range too large"):
            client.get("fbDomainShadowPrice", {})


def test_migration_matches_models():
    spec = importlib.util.spec_from_file_location("migration_91fa2b2f548a", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = mock.MagicMock()
    module.upgrade()

    metadata = sa.MetaData()
    tables = {c.args[0]: sa.Table(c.args[0], metadata, *c.args[1:]) for c in module.op.create_table.call_args_list}

    base_type = lambda t: t.impl if isinstance(t, sa.types.TypeDecorator) else t  # sqlmodel's AutoString wraps String
    describe = lambda table: (
        [(c.name, base_type(c.type).python_type, c.nullable) for c in table.columns],
        {(c.name, tuple(c.columns.keys())) for c in table.constraints if isinstance(c, sa.UniqueConstraint)},
        {(fk.parent.name, fk.target_fullname) for fk in table.foreign_keys},
    )
    for model in (BindingCnec, CnecPtdf):
        assert describe(tables[model.__tablename__]) == describe(model.__table__)

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import server


TOOLS = {
    "list_datasets", "describe_table", "get_coverage", "get_timeseries",
    "get_generation_units", "lookup_eic", "run_sql",
}


def test_all_tools_registered_as_read_only():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True
        assert t.annotations.destructive_hint is False


def test_dataset_value_columns_exist_on_models():
    for name, (model, columns, _) in server.DATASETS.items():
        for column in ["zone", "timestamp", "resolution", *columns]:
            assert column in model.model_fields, f"{name}.{column}"


def test_describe_table_known_and_unknown():
    columns = {c["column"] for c in server.describe_table("price")}
    assert {"zone", "timestamp", "price", "currency"} <= columns
    with pytest.raises(ToolError, match="Unknown table"):
        server.describe_table("pg_shadow")


@pytest.mark.parametrize("query", [
    "SELECT 1",
    "  select * from price;  ",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "explain select * from demand",
])
def test_validate_sql_accepts_reads(query):
    assert server.validate_sql(query)


@pytest.mark.parametrize("query", [
    "DELETE FROM price",
    "update price set price = 0",
    "SELECT 1; DROP TABLE price",
    "SET default_transaction_read_only = off",
    "",
])
def test_validate_sql_rejects_everything_else(query):
    with pytest.raises(ToolError):
        server.validate_sql(query)


def test_validate_range():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    server.validate_range(start, datetime(2025, 3, 31, tzinfo=timezone.utc))
    with pytest.raises(ToolError, match="90 days"):
        server.validate_range(start, datetime(2025, 6, 1, tzinfo=timezone.utc))
    with pytest.raises(ToolError, match="after start"):
        server.validate_range(start, datetime(2024, 1, 1, tzinfo=timezone.utc))


def test_unknown_dataset():
    with pytest.raises(ToolError, match="Unknown dataset"):
        server.get_coverage("prices")


def test_get_engine_requires_readonly_credentials(monkeypatch):
    server.get_engine.cache_clear()
    monkeypatch.setattr(server, "READONLY_USER", None)
    with pytest.raises(ToolError, match="READONLY_USER"):
        server.get_engine()
    server.get_engine.cache_clear()


def test_get_timeseries_treats_naive_as_utc_and_truncates(monkeypatch):
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    record = SimpleNamespace(timestamp=ts, resolution="PT60M", price=12.5, currency="EUR")
    fetch = mock.MagicMock(return_value=[record] * 3)
    monkeypatch.setattr(server, "fetch_timeseries", fetch)
    monkeypatch.setattr(server, "get_engine", mock.MagicMock())
    monkeypatch.setattr(server, "MAX_ROWS", 2)

    result = server.get_timeseries("price", "SE3", datetime(2025, 1, 1), datetime(2025, 1, 2))

    _, model, zone, start, end = fetch.call_args.args
    assert model is server.Price and zone == "SE3"
    assert start.tzinfo == timezone.utc and end.tzinfo == timezone.utc
    assert result["truncated"] is True
    assert result["rows"] == [{"timestamp": ts.isoformat(), "resolution": "PT60M", "price": 12.5, "currency": "EUR"}] * 2


def test_run_sql_limits_rows_and_rolls_back(monkeypatch):
    cursor = mock.MagicMock()
    cursor.description = [("zone",), ("n",)]
    cursor.fetchmany.return_value = [("SE1", 1), ("SE2", 2), ("SE3", 3)]
    connection = mock.MagicMock()
    connection.cursor.return_value = cursor
    engine = mock.MagicMock()
    engine.raw_connection.return_value = connection
    monkeypatch.setattr(server, "get_engine", lambda: engine)

    result = server.run_sql("SELECT zone, count(*) FROM price WHERE zone LIKE 'SE%' GROUP BY zone;", limit=2)

    cursor.execute.assert_called_once_with("SELECT zone, count(*) FROM price WHERE zone LIKE 'SE%' GROUP BY zone")
    cursor.fetchmany.assert_called_once_with(3)
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
    assert result == {"columns": ["zone", "n"], "truncated": True, "rows": [["SE1", 1], ["SE2", 2]]}

import asyncio
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


@pytest.mark.parametrize("query", [
    "  select * from price;  ",
    "WITH x AS (SELECT 1) SELECT * FROM x",
])
def test_validate_sql_accepts_reads(query):
    assert server.validate_sql(query)


@pytest.mark.parametrize("query", [
    "DELETE FROM price",
    "SELECT 1; DROP TABLE price",
    "SET default_transaction_read_only = off",
])
def test_validate_sql_rejects_everything_else(query):
    with pytest.raises(ToolError):
        server.validate_sql(query)


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

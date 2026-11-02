# MCP server

Read-only access to the shared electricity database for MCP clients (Claude Code, Claude Desktop), over stdio.

It connects as `READONLY_USER` / `READONLY_PASSWORD` from `platform/.env` (the SELECT-only role created in the first migration), and every transaction is additionally forced read-only with a 15 s statement timeout.

## Tools
- `list_datasets`: timeseries datasets, their value columns and meaning
- `describe_table`: columns and types of a table
- `get_coverage`: zones in a dataset, with row count and first/last timestamp
- `get_timeseries`: rows for one zone and date range (max 90 days / 10000 rows)
- `get_generation_units`: production resources and units of a zone as of a date
- `lookup_eic`: search the EIC registry by code or name
- `run_sql`: a single SELECT / WITH / EXPLAIN statement

## Running
1. bring the database up. The server runs on the host, so `DB_HOST` must resolve from there (default `localhost`)

    > % make infra-up

2. register it with Claude Code (run from `platform/`)

    > % claude mcp add electricity-db --env PYTHONPATH=$PWD/src -- $PWD/.venv/bin/python -m mcp_server

3. or run it by hand to debug

    > % make mcp

## Tests
> % pytest tests/test_mcp_server.py

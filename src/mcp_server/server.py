'''
Read-only MCP server over the shared electricity database.

Connects as READONLY_USER (SELECT-only role created in the first migration)
and additionally forces every transaction to be read-only with a statement
timeout, so even run_sql cannot write or hang the database.
'''
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import cache

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError  # message is shown to the client, unlike other exceptions
from mcp.types import ToolAnnotations
from sqlalchemy import create_engine, func, or_
from sqlmodel import Session, SQLModel, select

from master.config import READONLY_USER, READONLY_PASSWORD, READONLY_DATABASE_URL
from master.db.models import (
    Price, Demand, Weather, Irradiance, ProductionResource,
    CrossBorderCapacity, ZonePhysicalFlow, EicCode,
)
from master.db.queries import fetch_timeseries, fetch_graph


MAX_RANGE_DAYS = 90
MAX_ROWS = 10_000
STATEMENT_TIMEOUT_MS = 15_000

# dataset name -> (model, value columns returned next to timestamp/resolution, description)
DATASETS: dict[str, tuple] = {
    'price': (Price, ['price', 'currency'],
              "ENTSO-E 12.1.D day-ahead energy prices per bidding zone (e.g. 'SE3')."),
    'demand': (Demand, ['quantity', 'unit'],
               "ENTSO-E 6.1.A actual total load per bidding zone."),
    'weather': (Weather, ['fdir', 'ssrd', 'temperature_2m', 'wind_u_10m', 'wind_v_10m'],
                "Copernicus ERA5 single-level timeseries at each zone's reference point."),
    'irradiance': (Irradiance, ['sis', 'sid', 'unit'],
                   "EUMETSAT surface incoming shortwave (sis) and direct (sid) irradiance, W/m2."),
    'cross_border_capacity': (CrossBorderCapacity, ['flow_origin', 'flow_destination', 'quantity', 'unit'],
                              "ENTSO-E 11.3 DC link capacity. zone is a link key 'ORIGIN-DESTINATION' (e.g. 'NO2-DK1')."),
    'zone_physical_flow': (ZonePhysicalFlow, ['flow_origin', 'flow_destination', 'quantity', 'unit'],
                           "ENTSO-E 12.1.G physical flows. zone is a link key 'ORIGIN-DESTINATION' (e.g. 'SE3-FI')."),
}

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

SQL_ALLOWED_START = re.compile(r"^\s*(select|with|explain|show|table|values)\b", re.IGNORECASE)


mcp = MCPServer(
    name="electricity-db",
    instructions=(
        "Read-only access to the shared electricity research database (Nordic bidding zones). "
        "Start with list_datasets and get_coverage to see what exists, then get_timeseries for data. "
        "Timestamps are UTC. Use run_sql for aggregations the other tools don't cover."
    ),
)


@cache
def get_engine():
    if not READONLY_USER or not READONLY_PASSWORD:
        raise ToolError("READONLY_USER and READONLY_PASSWORD must be set (see platform/.env)")
    return create_engine(
        READONLY_DATABASE_URL,
        pool_size=2,
        pool_pre_ping=True,
        connect_args={"options": f"-c default_transaction_read_only=on -c statement_timeout={STATEMENT_TIMEOUT_MS}"},
    )


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _get_dataset(dataset: str) -> tuple:
    if dataset not in DATASETS:
        raise ToolError(f"Unknown dataset '{dataset}'. Must be one of {list(DATASETS)}")
    return DATASETS[dataset]


def validate_range(start: datetime, end: datetime):
    if end < start:
        raise ToolError("end must be after start")
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise ToolError(f"Date range cannot exceed {MAX_RANGE_DAYS} days")


def validate_sql(query: str) -> str:
    query = query.strip().rstrip(';').strip()
    if ';' in query:
        raise ToolError("Only a single statement is allowed")
    if not SQL_ALLOWED_START.match(query):
        raise ToolError("Only SELECT / WITH / EXPLAIN / SHOW / TABLE / VALUES queries are allowed")
    return query


@mcp.tool(annotations=READ_ONLY)
def list_datasets() -> list[dict]:
    """List the timeseries datasets with their value columns and meaning, plus the other tables."""
    datasets = [
        {"dataset": name, "table": model.__tablename__, "value_columns": columns, "description": description}
        for name, (model, columns, description) in DATASETS.items()
    ]
    datasets += [
        {"dataset": "generation_units", "table": f"{ProductionResource.__tablename__}, generating_unit",
         "value_columns": [], "description": "ENTSO-E master data of production resources and their units. Use get_generation_units."},
        {"dataset": "eic_code", "table": EicCode.__tablename__,
         "value_columns": [], "description": "ENTSO-E EIC registry. Use lookup_eic."},
    ]
    return datasets


@mcp.tool(annotations=READ_ONLY)
def describe_table(table: str) -> list[dict]:
    """Column names and types of a database table, e.g. 'price' or 'generating_unit'. Useful before run_sql."""
    if table not in SQLModel.metadata.tables:
        raise ToolError(f"Unknown table '{table}'. Must be one of {sorted(SQLModel.metadata.tables)}")
    return [
        {"column": c.name, "type": str(c.type), "nullable": c.nullable}
        for c in SQLModel.metadata.tables[table].columns
    ]


@mcp.tool(annotations=READ_ONLY)
def get_coverage(dataset: str, zone: str | None = None) -> list[dict]:
    """
    Which zones a timeseries dataset has, with row count and first/last timestamp per zone.
    Pass zone to restrict to one zone.
    """
    model, _, _ = _get_dataset(dataset)
    columns = [
        model.zone,
        func.count().label('rows'),
        func.min(model.timestamp).label('first_timestamp'),
        func.max(model.timestamp).label('last_timestamp'),
    ]
    if hasattr(model, 'fetched_at'):
        columns.append(func.max(model.fetched_at).label('last_fetched_at'))
    statement = select(*columns).group_by(model.zone).order_by(model.zone)
    if zone is not None:
        statement = statement.where(model.zone == zone)
    with Session(get_engine()) as session:
        rows = session.exec(statement).all()
    return [{key: _jsonable(value) for key, value in row._mapping.items()} for row in rows]


@mcp.tool(annotations=READ_ONLY)
def get_timeseries(dataset: str, zone: str, start: datetime, end: datetime) -> dict:
    """
    Rows of a timeseries dataset for one zone between start and end (inclusive, ISO 8601, UTC if no offset).
    The range is limited to 90 days and the result to 10000 rows; truncated says whether rows were cut.
    """
    model, value_columns, _ = _get_dataset(dataset)
    start, end = _as_utc(start), _as_utc(end)
    validate_range(start, end)
    with Session(get_engine()) as session:
        records = fetch_timeseries(session, model, zone, start, end)
    return {
        "dataset": dataset,
        "zone": zone,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "truncated": len(records) > MAX_ROWS,
        "rows": [
            {
                "timestamp": r.timestamp.isoformat(),
                "resolution": r.resolution,
                **{c: _jsonable(getattr(r, c)) for c in value_columns},
            }
            for r in records[:MAX_ROWS]
        ],
    }


@mcp.tool(annotations=READ_ONLY)
def get_generation_units(zone: str, as_of: date) -> list[dict]:
    """Production resources of a zone and their generating units, as registered on as_of (YYYY-MM-DD)."""
    with Session(get_engine()) as session:
        records = fetch_graph(session, ProductionResource, zone, as_of)
        return [
            {
                "resource_mrid": r.resource_mrid,
                "resource_name": r.resource_name,
                "location_name": r.location_name,
                "psr_type": r.psr_type,
                "nominal_p_mw": r.nominal_p_mw,
                "implementation_date": r.implementation_date.isoformat(),
                "units": [
                    {
                        "unit_mrid": u.unit_mrid,
                        "name": u.name,
                        "nominal_p_mw": u.nominal_p_mw,
                        "psr_type": u.psr_type,
                        "location_name": u.location_name,
                    }
                    for u in r.units
                ],
            }
            for r in records
        ]


@mcp.tool(annotations=READ_ONLY)
def lookup_eic(query: str, limit: int = 20) -> list[dict]:
    """Search the EIC registry by code or by (part of) its long or display name."""
    pattern = f"%{query}%"
    statement = select(EicCode).where(or_(
        EicCode.eic_code.ilike(pattern),
        EicCode.long_name.ilike(pattern),
        EicCode.display_name.ilike(pattern),
    )).order_by(EicCode.eic_code).limit(min(limit, 200))
    with Session(get_engine()) as session:
        records = session.exec(statement).all()
    return [
        {
            "eic_code": r.eic_code,
            "long_name": r.long_name,
            "display_name": r.display_name,
            "eic_parent": r.eic_parent,
            "functions": r.functions,
        }
        for r in records
    ]


@mcp.tool(annotations=READ_ONLY)
def run_sql(query: str, limit: int = 1000) -> dict:
    """
    Run one read-only SQL query (SELECT / WITH / EXPLAIN ...) against the database.
    Runs as a SELECT-only role in a read-only transaction with a 15 s timeout. At most 10000 rows are returned.
    """
    query = validate_sql(query)
    limit = max(1, min(limit, MAX_ROWS))
    connection = get_engine().raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(query)  # no params, so '%' in the query is taken literally
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(limit + 1) if columns else []
        connection.rollback()
    finally:
        connection.close()
    return {
        "columns": columns,
        "truncated": len(rows) > limit,
        "rows": [[_jsonable(v) for v in row] for row in rows[:limit]],
    }

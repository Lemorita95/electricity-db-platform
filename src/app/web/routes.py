from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from datetime import date, datetime
import threading
import json
from pathlib import Path

from master.db.connection import get_session
from master.db.models import Price, Demand, Weather, ProductionResource, CrossBorderCapacity, ZonePhysicalFlow
from master.db.queries import fetch_timeseries, fetch_graph
from managers.config import NORDICS_CODES, LINKS
from managers.sync import sync, SOURCES
from managers import copernicus_client, entsoe_client


BASE = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE / "templates"

fetch_lock = threading.Lock()
fetch_status_map: dict[str, dict] = {name: {"status": "idle"} for name in SOURCES}

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

MAX_RANGE_DAYS = 90
WEATHER_COLUMNS = ['fdir', 'ssrd', 'temperature_2m', 'wind_u_10m', 'wind_v_10m']


def validate_range(start: datetime, end: datetime):
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days"
        )


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/entsoe", response_class=HTMLResponse)
def entsoe_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="entsoe.html",
        context={"zones": list(NORDICS_CODES.keys())}
    )


@router.get("/generation_units", response_class=HTMLResponse)
def generation_units_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="generation_units.html",
        context={"zones": list(NORDICS_CODES.keys())}
    )


@router.get("/copernicus", response_class=HTMLResponse)
def copernicus_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="copernicus.html",
        context={"zones": list(NORDICS_CODES.keys()), "weather_columns": WEATHER_COLUMNS}
    )


@router.get("/physical_flow", response_class=HTMLResponse)
def physical_flow_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="physical_flow.html",
        context={"zones": list(NORDICS_CODES), "links_json": json.dumps(LINKS)}
    )


@router.get("/api/price")
def get_price_snapshot(zone: str, start: datetime, end: datetime, session: Session = Depends(get_session)):
    validate_range(start, end)
    records = fetch_timeseries(session, Price, zone, start, end)
    return [{"timestamp": r.timestamp.isoformat(), "price": r.price} for r in records if r.price is not None]


@router.get("/api/demand")
def get_demand_snapshot(zone: str, start: datetime, end: datetime, session: Session = Depends(get_session)):
    validate_range(start, end)
    records = fetch_timeseries(session, Demand, zone, start, end)
    return [{"timestamp": r.timestamp.isoformat(), "quantity": r.quantity} for r in records if r.quantity is not None]


@router.get("/api/capacity")
def get_capacity_snapshot(link: str, start: datetime, end: datetime, session: Session = Depends(get_session)):
    validate_range(start, end)
    records = fetch_timeseries(session, CrossBorderCapacity, link, start, end)
    return [{"timestamp": r.timestamp.isoformat(), "quantity": r.quantity} for r in records if r.quantity is not None]


@router.get("/api/physical_flow")
def get_physical_flow_snapshot(link: str, start: datetime, end: datetime, session: Session = Depends(get_session)):
    validate_range(start, end)
    records = fetch_timeseries(session, ZonePhysicalFlow, link, start, end)
    return [{"timestamp": r.timestamp.isoformat(), "quantity": r.quantity} for r in records if r.quantity is not None]



@router.get("/api/generation_units")
def get_generation_units_snapshot(zone: str, as_of: date, session: Session = Depends(get_session)):
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


@router.get("/api/weather")
def get_weather_snapshot(zone: str, start: datetime, end: datetime, column: str, session: Session = Depends(get_session)):
    if column not in WEATHER_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid column: {column}")
    validate_range(start, end)
    records = fetch_timeseries(session, Weather, zone, start, end)
    return [{"timestamp": r.timestamp.isoformat(), "value": getattr(r, column)} for r in records if getattr(r, column) is not None]


def _run_in_background(source: str, start: datetime | None = None, end: datetime | None = None):
    with fetch_lock:
        if fetch_status_map[source]["status"] == "running":
            return False
        fetch_status_map[source]["status"] = "queued"

    def run():
        fetch_status_map[source]["status"] = "running"
        fetch_status_map[source]["progress"] = {}

        def progress_callback(key, msg, source_name):
            fetch_status_map[source]["progress"].setdefault(key, {})[source_name] = msg

        try:
            sync(source=source, start=start, end=end, progress_callback=progress_callback)
            fetch_status_map[source]["status"] = "done"
        except Exception as e:
            fetch_status_map[source]["status"] = "failed"
            fetch_status_map[source]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return True


@router.post("/api/fetch")
def trigger_fetch(source: str, start: datetime | None = None, end: datetime | None = None):
    valid_sources = list(fetch_status_map.keys())
    if source not in valid_sources:
        raise HTTPException(status_code=400, detail=f"Invalid source. Must be one of {valid_sources}")
    started = _run_in_background(source, start, end)
    if not started:
        raise HTTPException(status_code=409, detail="Fetch already running for this source")
    return {"status": "started", "source": source}


@router.get("/api/fetch/status")
def fetch_status():
    return {
        **fetch_status_map,
        "rates": {
            "entsoe": entsoe_client.monitor.rate,
            "copernicus": copernicus_client.monitor.rate,
        },
    }
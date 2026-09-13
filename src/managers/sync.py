from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlmodel import Session, SQLModel
from dataclasses import dataclass
from typing import Callable, Type, Literal

from master.db.connection import engine
from master.db.queries import upsert_timeseries, get_timestamps, upsert_graph
from master.db.models import Price, Demand, ProductionResource, Weather

from managers.config import EIC_CODES
from managers import get_price, get_demand, get_generation_units, get_era5


@dataclass(frozen=True)
class Source:
    model: Type[SQLModel]
    fetch_fn: Callable
    save_fn: Callable
    fetch_kind: Literal['range', 'cursor'] = 'range'

SOURCES: dict[str, Source] = {
    'entsoe_price': Source(Price, get_price, upsert_timeseries),
    'entsoe_demand': Source(Demand, get_demand, upsert_timeseries),
    'generation_units': Source(ProductionResource, get_generation_units, upsert_graph, fetch_kind='cursor'),
    'copernicus': Source(Weather, get_era5, upsert_timeseries),
}

def get_fetch_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)


def get_fetch_end() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _fetch_range(session, zone, start, end, src, cb):
    status = get_timestamps(session, src.model, zone, start, end)
    if not status['missing_ranges']:
        return None
    records = []
    for gap in status['missing_ranges']:
        batch = src.fetch_fn(zone, gap["start"], gap["end"], progress_callback=cb)
        if batch:
            records.extend(batch)
    return records


def _fetch_cursor(zone, start, src, cb):
    return src.fetch_fn(zone, start, progress_callback=cb)


def fetch_zone_date_source(zone: str, start: datetime, end: datetime, source: str, progress_callback=None):
    if source not in SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    src = SOURCES[source]

    def cb(msg, q=source):
        if progress_callback:
            progress_callback(msg, q)

    try:
        with Session(engine) as session:
            if src.fetch_kind == 'cursor':
                records = _fetch_cursor(zone, start, src, cb)
            else:
                records = _fetch_range(session, zone, start, end, src, cb)
                if records is None:
                    if progress_callback:
                        progress_callback("up-to-date", source)
                    return

            if records:
                src.save_fn(session, src.model, records)
                if progress_callback:
                    progress_callback("done", source)
            else:
                if progress_callback:
                    progress_callback("up-to-date", source)
    except Exception as e:
        if progress_callback:
            progress_callback(f"failed: {e}", source)
        raise


def fetch_zone_date(zone: str, start: datetime, end: datetime, progress_callback=None) -> None:
    for source in SOURCES.keys():
        fetch_zone_date_source(zone, start, end, source, progress_callback=progress_callback)


def sync(start: datetime | None = None, end: datetime | None = None, source: str | None = None, progress_callback=None) -> dict:
    if end is None:
        end = get_fetch_end()
    if start is None:
        start = get_fetch_start()

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for zone in EIC_CODES:
            callback = lambda msg, q='', z=zone: progress_callback(z, msg, q) if progress_callback else None
            if (source == 'all') or source is None:
                future = executor.submit(fetch_zone_date, zone, start, end, progress_callback=callback)
            else:
                future = executor.submit(fetch_zone_date_source, zone, start, end, source, progress_callback=callback)
            futures[future] = zone

        for future in as_completed(futures):
            zone = futures[future]
            try:
                future.result()
                results[zone] = 'done'
            except Exception as e:
                results[zone] = f"failed: {e}"

    return results

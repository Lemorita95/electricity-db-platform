from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlmodel import Session, SQLModel
from dataclasses import dataclass, field
from typing import Callable, Type, Literal

from master.db.connection import engine
from master.db.queries import upsert_timeseries, get_timestamps, upsert_graph
from master.db.models import Price, Demand, ProductionResource, Weather, \
    CrossBorderCapacity, ZonePhysicalFlow

from managers.config import NORDICS_CODES, LINKS
from managers import get_price, get_demand, get_generation_units, get_era5, \
    get_cross_border_capacity, get_zone_physical_flows


@dataclass(frozen=True)
class Source:
    model: Type[SQLModel]
    fetch_fn: Callable
    save_fn: Callable
    fetch_kind: Literal['range', 'cursor'] = 'range'
    keys: dict = field(default_factory=lambda: NORDICS_CODES)


SOURCES: dict[str, Source] = {
    # ENDPOINT_NAME: Source(DB_MODEL, FETCH_FN, SAVE_FN, FETCH_FIND, KEYS)

    'entsoe_price': Source(Price, get_price, upsert_timeseries, fetch_kind='range', keys=NORDICS_CODES),
    'entsoe_demand': Source(Demand, get_demand, upsert_timeseries, fetch_kind='range', keys=NORDICS_CODES),
    'generation_units': Source(ProductionResource, get_generation_units, upsert_graph, fetch_kind='cursor', keys=NORDICS_CODES),
    'cross_border_capacity': Source(CrossBorderCapacity, get_cross_border_capacity, upsert_timeseries, keys=LINKS),
    'zone_physical_flows': Source(ZonePhysicalFlow, get_zone_physical_flows, upsert_timeseries, keys=LINKS),
    'copernicus': Source(Weather, get_era5, upsert_timeseries, fetch_kind='range', keys=NORDICS_CODES),
}


def get_fetch_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)


def get_fetch_end() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _get_missing_ranges(key, start, end, src) -> list[dict]:
    with Session(engine) as session:
        status = get_timestamps(session, src.model, key, start, end)
    return status['missing_ranges']


def _fetch_range(key, start, end, src, cb):
    missing_ranges = _get_missing_ranges(key, start, end, src)
    if not missing_ranges:
        return None
    records = []
    for gap in missing_ranges:
        batch = src.fetch_fn(key, gap["start"], gap["end"], progress_callback=cb)
        if batch:
            records.extend(batch)
    return records


def _fetch_cursor(key, start, src, cb):
    return src.fetch_fn(key, start, progress_callback=cb)


def fetch_key_source(key: str, start: datetime, end: datetime, source_name: str, progress_callback=None) -> None:
    src = SOURCES[source_name]

    def cb(msg):
        if progress_callback:
            progress_callback(msg)

    try:
        if src.fetch_kind == 'cursor':
            records = _fetch_cursor(key, start, src, cb)
        else:
            records = _fetch_range(key, start, end, src, cb)
            if records is None:
                if progress_callback:
                    progress_callback("up-to-date")
                return

        if records:
            with Session(engine) as session:
                src.save_fn(session, src.model, records)
            if progress_callback:
                progress_callback("done")
        else:
            if progress_callback:
                progress_callback("up-to-date")
    except Exception as e:
        if progress_callback:
            progress_callback(f"failed: {e}")
        raise


def sync(source: str, start: datetime | None = None, end: datetime | None = None, progress_callback=None) -> dict:
    if source not in SOURCES:
        raise ValueError(f"Unsupported source: {source}")

    if end is None:
        end = get_fetch_end()
    if start is None:
        start = get_fetch_start()

    src = SOURCES[source]
    results: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for key in src.keys:
            cb = (lambda msg, k=key: progress_callback(k, msg, source)) if progress_callback else None
            future = executor.submit(fetch_key_source, key, start, end, source, progress_callback=cb)
            futures[future] = key

        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
                results[key] = 'done'
            except Exception as e:
                results[key] = f"failed: {e}"

    return results
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlmodel import Session, SQLModel
from dataclasses import dataclass
from typing import Callable, Type

from master.db.connection import engine
from master.db.queries import upsert, get_timestamps
from master.db.models import Price, Demand, Weather

from managers.config import EIC_CODES
from managers import get_price, get_demand, get_era5 # endpoints


@dataclass(frozen=True)
class Source:
    model: Type[SQLModel]
    fetch_fn: Callable

SOURCES: dict[str, Source] = {
    'entsoe_price': Source(model=Price, fetch_fn=get_price),
    'entsoe_demand': Source(model=Demand, fetch_fn=get_demand),
    'copernicus': Source(model=Weather, fetch_fn=get_era5),
}


def get_fetch_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)


def get_fetch_end() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def fetch_zone_date_source(zone: str, start: datetime, end: datetime, source: str, progress_callback=None) -> None:
    if source not in SOURCES.keys():
        raise ValueError(f"Unsupported source: {source}")

    model = SOURCES[source].model
    fetch_fn = SOURCES[source].fetch_fn

    with Session(engine) as session:
        status = get_timestamps(session, model, zone, start, end)

        missing_ranges = status['missing_ranges']

        if not missing_ranges:
            if progress_callback:
                progress_callback("up-to-date", source)
            return

        def cb(msg, q=source):
            if progress_callback:
                progress_callback(msg, q)

        try:
            all_records = []
            
            # fetch first, aggregate second
            for gap in missing_ranges:
                batch = fetch_fn(zone, gap["start"], gap["end"], progress_callback=cb)
                if batch:
                    all_records.extend(batch)

            if all_records:
                upsert(session, model, all_records)
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

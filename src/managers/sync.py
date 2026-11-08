import threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlmodel import Session, SQLModel
from dataclasses import dataclass, field
from typing import Callable, Type, Literal
from collections.abc import Iterator

from master.db.connection import engine
from master.db.queries import upsert_timeseries, get_timestamps, upsert_graph
from master.db.models import Price, Demand, ProductionResource, Weather, \
    DcLinkTransferLimit, ZonePhysicalFlow, EicCode, BindingCnec, Generation, WindSolarForecast, \
    LoadForecast, HydroReservoir, FbBorderFlow

from managers.config import NORDICS_CODES, PRICE_ZONES, HYDRO_RESERVOIR_ZONES, LINKS, DC_LINKS
from managers import get_price, get_demand, get_generation_units, get_era5, \
    get_dc_link_transfer_limit, get_zone_physical_flow, get_eic_code, get_binding_cnecs, \
    get_generation, get_wind_solar_forecast, get_load_forecast, get_hydro_reservoir, \
    get_fb_monitoring


@dataclass(frozen=True)
class Source:
    model: Type[SQLModel]
    fetch_fn: Callable
    save_fn: Callable
    fetch_kind: Literal['range', 'cursor'] = 'range'
    keys: dict = field(default_factory=lambda: NORDICS_CODES)
    merge_gaps: timedelta | None = None  # gaps this close are fetched as one range; None fetches each gap exactly


# ENTSO-E answers even a 15-min window with the whole day, in ~15 s
ENTSOE_MERGE_GAPS = timedelta(days=1)


def upsert_by_model(session, model, records: list) -> None:
    '''saves a batch that mixes models, each record into its own table; `model` is the one gaps are read from'''
    by_model = {}
    for record in records:
        by_model.setdefault(type(record), []).append(record)
    for record_model, batch in by_model.items():
        upsert_timeseries(session, record_model, batch)


def _entsoe(model, fetch_fn, keys=NORDICS_CODES) -> Source:
    return Source(model, fetch_fn, upsert_timeseries, keys=keys, merge_gaps=ENTSOE_MERGE_GAPS)


SOURCES: dict[str, Source] = {
    # ENDPOINT_NAME: Source(DB_MODEL, FETCH_FN, SAVE_FN, FETCH_KIND, KEYS, MERGE_GAPS)

    'entsoe_price': _entsoe(Price, get_price, keys=PRICE_ZONES),
    'entsoe_demand': _entsoe(Demand, get_demand),
    'entsoe_generation': _entsoe(Generation, get_generation),
    'entsoe_wind_solar_forecast': _entsoe(WindSolarForecast, get_wind_solar_forecast),
    'entsoe_load_forecast': _entsoe(LoadForecast, get_load_forecast),
    'entsoe_hydro_reservoir': _entsoe(HydroReservoir, get_hydro_reservoir, keys=HYDRO_RESERVOIR_ZONES),
    'entsoe_dc_link_transfer_limit': _entsoe(DcLinkTransferLimit, get_dc_link_transfer_limit, keys=DC_LINKS),
    'zone_physical_flow': _entsoe(ZonePhysicalFlow, get_zone_physical_flow, keys=LINKS),
    'generation_units': Source(ProductionResource, get_generation_units, upsert_graph, fetch_kind='cursor'),
    'copernicus': Source(Weather, get_era5, upsert_timeseries),
    'eic_codes': Source(EicCode, get_eic_code, upsert_timeseries, fetch_kind='cursor', keys={'ALL': {}}),
    'jao_binding_cnec': Source(BindingCnec, get_binding_cnecs, upsert_graph, keys={'NORDIC': {}}),
    # one request fills both tables; gaps are read from fb_border_flow
    'jao_fb_monitoring': Source(FbBorderFlow, get_fb_monitoring, upsert_by_model, keys={'NORDIC': {}}),
}


def get_fetch_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)


def get_fetch_end() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _get_missing_ranges(key, start, end, src) -> list[dict]:
    with Session(engine) as session:
        status = get_timestamps(session, src.model, key, start, end)
    return status['missing_ranges']


def _as_batches(result):
    '''an iterator must yield lists of records (one list per batch); anything else is a single batch'''
    if isinstance(result, Iterator):
        yield from result # for example: get_price, get_zone_physical_flow
    else:
        yield result # for example: get_generation_units


def _merge_gaps(gaps: list[dict], max_distance: timedelta) -> list[dict]:
    '''
    gaps at most max_distance apart chain into one min(start) -> max(end) range;
    the stored data in between is fetched again
    '''
    merged = []
    for gap in gaps:
        if merged and gap["start"] - merged[-1]["end"] <= max_distance:
            merged[-1] = {"start": merged[-1]["start"], "end": gap["end"]}
        else:
            merged.append(dict(gap))
    return merged


def _fetch_range(key, start, end, src, cb):
    missing_ranges = _get_missing_ranges(key, start, end, src)
    if src.merge_gaps is not None:
        missing_ranges = _merge_gaps(missing_ranges, src.merge_gaps)

    if not missing_ranges:
        return None

    def batches():
        for gap in missing_ranges:
            result = src.fetch_fn(
                key, gap["start"], gap["end"],
                progress_callback=cb
            )
            yield from _as_batches(result)

    return batches()


def _fetch_cursor(key, start, src, cb):
    result = src.fetch_fn(key, start, progress_callback=cb)
    return _as_batches(result)


def fetch_key_source(key: str, start: datetime, end: datetime, source_name: str, progress_callback=None,
                     cancel_event: threading.Event | None = None) -> None:
    '''cancel_event is checked before the first request and after each saved batch'''
    src = SOURCES[source_name]

    def cb(msg):
        if progress_callback:
            progress_callback(msg)

    saved_chunks = 0
    cancelled = lambda: cancel_event is not None and cancel_event.is_set()

    if cancelled():
        cb("cancelled")
        return

    try:
        if src.fetch_kind == 'cursor':
            batches = _fetch_cursor(key, start, src, cb)
        else:
            batches = _fetch_range(key, start, end, src, cb)

            if batches is None:
                if progress_callback:
                    progress_callback("up-to-date")
                return

        for records in batches:
            if records:
                with Session(engine) as session:
                    src.save_fn(session, src.model, records)
                saved_chunks += 1

            if cancelled():
                cb(f"cancelled after saving {saved_chunks} chunks")
                return

        if progress_callback:
            progress_callback("done" if saved_chunks else "up-to-date")

    except Exception as e:
        if progress_callback:
            if saved_chunks:
                progress_callback(
                    f"failed after saving {saved_chunks} chunks: {e}"
                )
            else:
                progress_callback(f"failed: {e}")
        e.saved_chunks = saved_chunks  # read by sync() for the per-key result
        raise


def sync(source: str, start: datetime | None = None, end: datetime | None = None, progress_callback=None,
         cancel_event: threading.Event | None = None) -> dict:
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
            future = executor.submit(fetch_key_source, key, start, end, source, progress_callback=cb, cancel_event=cancel_event)
            futures[future] = key

        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
                results[key] = 'done'
            except Exception as e:
                saved = getattr(e, 'saved_chunks', 0)
                results[key] = f"failed after saving {saved} chunks: {e}" if saved else f"failed: {e}"

    return results
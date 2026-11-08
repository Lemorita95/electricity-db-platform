from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Iterator

from managers.config import NORDICS_CODES, QUERY_CONFIGS
from master.db.models import Weather

from managers.copernicus.copernicus_client import CopernicusClient
from managers.copernicus.copernicus_parser import parse_weather
from managers.chunks import chunk_by_period, display
from managers.shared import shared


get_copernicus_client = shared(CopernicusClient)

cfg = QUERY_CONFIGS['copernicus']

ERA5_LAG = timedelta(days=5)  # ERA5 reaches D-5


def _available_until() -> datetime:
    '''exclusive end of the published data: midnight UTC, five days ago'''
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today - ERA5_LAG


def _build_request(zone: str, start: datetime, end: datetime) -> dict:
    request = deepcopy(cfg['request'])
    request['location'] = {
        'longitude': NORDICS_CODES[zone]['lon'],
        'latitude': NORDICS_CODES[zone]['lat'],
    }
    # CDS dates are inclusive and end is exclusive, so the last day asked for is the one before end
    last_day = end - timedelta(microseconds=1)
    request['date'] = [f"{start:%Y-%m-%d}/{last_day:%Y-%m-%d}"]
    return request


def get_era5(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[Weather]]:
    '''yields one list per 30-day chunk; nothing is asked past what ERA5 has published'''
    end = min(end, _available_until())
    chunks = chunk_by_period(start, end, '30d')

    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(
                f"era5 {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}"
            )

        request = _build_request(zone, chunk_start, chunk_end)
        results = get_copernicus_client().retrieve(cfg['dataset'], request)
        yield parse_weather(results, zone)

from copy import deepcopy
from datetime import datetime

from managers.config import EIC_CODES, QUERY_CONFIGS
from master.db.models import Weather

from managers.copernicus.copernicus_client import CopernicusClient
from managers.copernicus.copernicus_parser import parse_weather
from managers.chunks import chunk_by_period, display


copernicus_client = CopernicusClient()
cfg = QUERY_CONFIGS['copernicus']


def _build_request(zone: str, start: datetime, end: datetime) -> dict:
    request = deepcopy(cfg['request'])
    request['location'] = {
        'longitude': EIC_CODES[zone]['lon'],
        'latitude': EIC_CODES[zone]['lat'],
    }
    request['date'] = [f"{start:%Y-%m-%d}/{end:%Y-%m-%d}"]
    return request


def get_era5(zone: str, start: datetime, end: datetime, progress_callback=None) -> list[Weather]:
    all_results = []
    chunks = chunk_by_period(start, end, '30d')

    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(
                f"era5 {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}"
            )

        request = _build_request(zone, chunk_start, chunk_end)
        results = copernicus_client.retrieve(cfg['dataset'], request)
        all_results.extend(parse_weather(results, zone))

    return all_results

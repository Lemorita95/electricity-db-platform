from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from managers.config import EIC_CODES, QUERY_CONFIGS
from master.db.models import Irradiance

from managers.eumet.eumet_client import EumetClient
from managers.eumet.eumet_parser import parse_irradiance
from managers.chunks import chunk_by_period, display

eumet_client = EumetClient()

SPATIAL_RESOLUTION = 0.05
MAX_WORKERS = 15

cfg = QUERY_CONFIGS['eumet']


def _point_bbox(zone: str) -> str:
    lat = EIC_CODES[zone]['lat']
    lon = EIC_CODES[zone]['lon']
    return (
        f"{lon - SPATIAL_RESOLUTION},{lat - SPATIAL_RESOLUTION},"
        f"{lon + SPATIAL_RESOLUTION},{lat + SPATIAL_RESOLUTION}"
    )


def _fetch(collection, dtstart: datetime, dtend: datetime, bbox: str, var_type: str):
    return list(collection.search(
        sat=cfg['sat'],
        type=var_type,
        compositeType=cfg['compositeType'],
        statisticType=cfg['statisticType'],
        dtstart=dtstart,
        dtend=dtend,
        bbox=bbox,
    ))


def get_sarah3(zone: str, start: datetime, end: datetime, progress_callback=None) -> list[Irradiance]:
    collection = eumet_client.get_collection(cfg['collectionID'])
    bbox = _point_bbox(zone)
    chunks = chunk_by_period(start, end, '30d')
    all_results = []

    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(
                f"sarah3 {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}"
            )

        all_products = []
        for var in cfg["var_type"]:
            all_products.extend(
                (product, var) for product in _fetch(collection, chunk_start, chunk_end, bbox, var_type=var)
            )

        chunk_result = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(parse_irradiance, product, zone, var): (product, var)
                for product, var in all_products
            }
            for future in as_completed(futures):
                chunk_result.extend(future.result())

        all_results.extend(chunk_result)

    return all_results
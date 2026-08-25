from datetime import datetime
import requests
import xml.etree.ElementTree as ET

from managers.config import EIC_CODES, QUERY_CONFIGS
from master.db.models import Price, Demand

from managers.entsoe.entsoe_client import EntsoClient
from managers.entsoe.entsoe_parser import parse_price, parse_demand, parse_eic_code
from managers.chunks import chunk_by_period, display

entsoe_client = EntsoClient()


def _fetch(params, parse_fn, zone):
    return parse_fn(entsoe_client.get(params), zone)


def _paginate(params, parse_fn, zone):
    all_results = []
    offset = 0
    while True:
        results = parse_fn(entsoe_client.get({**params, 'offset': offset}), zone)
        all_results.extend(results)
        if len(results) < 100:
            break
        offset += 100
    return all_results


def get_price(zone: str, start: datetime, end: datetime, progress_callback=None) -> list[Price]:
    cfg = QUERY_CONFIGS['price']
    all_results = []
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"price {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'contract_MarketAgreement.type': cfg['contract_MarketAgreement.type'],
            'in_Domain': EIC_CODES[zone]['eic'],
            'out_Domain': EIC_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        all_results.extend(_paginate(params, parse_price, zone))
    return all_results


def get_demand(zone: str, start: datetime, end: datetime, progress_callback=None) -> list[Demand]:
    cfg = QUERY_CONFIGS['demand']
    all_results = []
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"demand {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'processType': cfg['processType'],
            'outBiddingZone_Domain': EIC_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        all_results.extend(_fetch(params, parse_demand, zone))
    return all_results


def get_eic_code(function_filter: str = None) -> list:
    url = "https://eepublicdownloads.blob.core.windows.net/cio-lio/xml/allocated-eic-codes.xml"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return parse_eic_code(root, function_filter)
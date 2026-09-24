from datetime import datetime
import requests
import xml.etree.ElementTree as ET

from master.db.models import Price, Demand, ProductionResource, \
        CrossBorderCapacity, ZonePhysicalFlow

from managers.config import EIC_CODES, NORDICS_CODES, QUERY_CONFIGS, LINKS
from managers.entsoe.entsoe_client import EntsoClient
from managers.entsoe.entsoe_parser import parse_price, parse_demand, parse_generation_units, \
    parse_cross_border_capacity, parse_eic_code, parse_zone_physical_flow
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
    '''
        resolve price for a single 'key' (zone)
    '''
    cfg = QUERY_CONFIGS['price']
    all_results = []
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"price {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'contract_MarketAgreement.type': cfg['contract_MarketAgreement.type'],
            'in_Domain': NORDICS_CODES[zone]['eic'],
            'out_Domain': NORDICS_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        all_results.extend(_paginate(params, parse_price, zone))
    return all_results


def get_demand(zone: str, start: datetime, end: datetime, progress_callback=None) -> list[Demand]:
    '''
        resolve demand for a single 'key' (zone)
    '''
    cfg = QUERY_CONFIGS['demand']
    all_results = []
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"demand {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'processType': cfg['processType'],
            'outBiddingZone_Domain': NORDICS_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        all_results.extend(_fetch(params, parse_demand, zone))
    return all_results


def get_generation_units(zone: str, start: datetime, progress_callback=None) -> list[ProductionResource]:
    '''
        resolve generation units for a single 'key' (zone)
    '''
    cfg = QUERY_CONFIGS['generation_units']

    if progress_callback:
        progress_callback(f"generation units — from {display(start)}")

    params = {
        'documentType': cfg['documentType'],
        'businessType': cfg['businessType'],
        'BiddingZone_Domain': NORDICS_CODES[zone]['eic'],
        'Implementation_DateAndOrTime': start.strftime('%Y-%m-%d'),
    }

    return _fetch(params, parse_generation_units, zone)


def get_cross_border_capacity(key: str, start: datetime, end: datetime, progress_callback=None) -> list[CrossBorderCapacity]:
    '''
        resolve cross border capacity for a single 'key' (link)
    '''
    cfg = QUERY_CONFIGS['cross_border_capacity']
    link = LINKS[key]
    all_results = []
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"cross_border_capacity {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'curveType': cfg['curveType'],
            'in_Domain': EIC_CODES[link['destination']]['eic'],
            'out_Domain': EIC_CODES[link['origin']]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        all_results.extend(_fetch(params, parse_cross_border_capacity, key))
    return all_results


def get_zone_physical_flow(key: str, start: datetime, end: datetime, progress_callback=None) -> list[ZonePhysicalFlow]:
    '''
        resolve zone physical flow for a single 'key' (link)
    '''
    cfg = QUERY_CONFIGS['zone_physical_flow']
    link = LINKS[key]
    all_results = []
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"zone_physical_flow {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'curveType': cfg['curveType'],
            'in_Domain': EIC_CODES[link['destination']]['eic'],
            'out_Domain': EIC_CODES[link['origin']]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        all_results.extend(_fetch(params, parse_zone_physical_flow, key))
    return all_results


def get_eic_code(function_filter: str = None) -> list:
    url = "https://eepublicdownloads.blob.core.windows.net/cio-lio/xml/allocated-eic-codes.xml"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return parse_eic_code(root, function_filter)
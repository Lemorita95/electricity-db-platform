from datetime import datetime
from functools import cache
from typing import Iterator
import requests
import xml.etree.ElementTree as ET

from master.db.models import Price, Demand, ProductionResource, \
        CrossBorderCapacity, ZonePhysicalFlow, Generation, WindSolarForecast, LoadForecast, HydroReservoir

from managers.config import EIC_CODES, NORDICS_CODES, PRICE_ZONES, QUERY_CONFIGS, LINKS
from managers.entsoe.entsoe_client import EntsoClient
from managers.entsoe.entsoe_parser import parse_price, parse_demand, parse_generation_units, \
    parse_cross_border_capacity, parse_eic_code, parse_zone_physical_flow, parse_generation, \
    parse_wind_solar_forecast, parse_load_forecast, parse_hydro_reservoir
from managers.chunks import chunk_by_period, display


@cache
def get_entsoe_client() -> EntsoClient:
    return EntsoClient()


def _fetch(params, parse_fn, zone):
    return parse_fn(get_entsoe_client().get(params), zone)


def _paginate(params, parse_fn, zone):
    all_results = []
    offset = 0
    while True:
        results = parse_fn(get_entsoe_client().get({**params, 'offset': offset}), zone)
        all_results.extend(results)
        if len(results) < 100:
            break
        offset += 100
    return all_results


def get_price(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[Price]]:
    '''
        resolve price for a single 'key' (zone), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['price']
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"price {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'contract_MarketAgreement.type': cfg['contract_MarketAgreement.type'],
            'in_Domain': PRICE_ZONES[zone]['eic'],
            'out_Domain': PRICE_ZONES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        yield _paginate(params, parse_price, zone)


def get_demand(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[Demand]]:
    '''
        resolve demand for a single 'key' (zone), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['demand']
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
        yield _fetch(params, parse_demand, zone)


def get_generation(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[Generation]]:
    '''
        resolve actual generation per production type for a single 'key' (zone), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['generation']
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"generation {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'processType': cfg['processType'],
            'in_Domain': NORDICS_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        yield _fetch(params, parse_generation, zone)


def get_wind_solar_forecast(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[WindSolarForecast]]:
    '''
        resolve day-ahead wind and solar forecasts for a single 'key' (zone), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['wind_solar_forecast']
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"wind_solar_forecast {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'processType': cfg['processType'],
            'in_Domain': NORDICS_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        yield _fetch(params, parse_wind_solar_forecast, zone)


def get_load_forecast(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[LoadForecast]]:
    '''
        resolve the day-ahead load forecast for a single 'key' (zone), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['load_forecast']
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"load_forecast {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'processType': cfg['processType'],
            'outBiddingZone_Domain': NORDICS_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        yield _fetch(params, parse_load_forecast, zone)


def get_hydro_reservoir(zone: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[HydroReservoir]]:
    '''
        resolve weekly reservoir filling for a single 'key' (zone), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['hydro_reservoir']
    chunks = chunk_by_period(start, end, '30d')
    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"hydro_reservoir {i}/{len(chunks)} — {display(chunk_start)} → {display(chunk_end)}")
        params = {
            'documentType': cfg['documentType'],
            'processType': cfg['processType'],
            'in_Domain': NORDICS_CODES[zone]['eic'],
            'periodStart': chunk_start.strftime('%Y%m%d%H%M'),
            'periodEnd': chunk_end.strftime('%Y%m%d%H%M'),
        }
        yield _fetch(params, parse_hydro_reservoir, zone)


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


def get_cross_border_capacity(key: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[CrossBorderCapacity]]:
    '''
        resolve cross border capacity for a single 'key' (link), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['cross_border_capacity']
    link = LINKS[key]
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
        yield _fetch(params, parse_cross_border_capacity, key)


def get_zone_physical_flow(key: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[ZonePhysicalFlow]]:
    '''
        resolve zone physical flow for a single 'key' (link), yielding one list per 30-day chunk
    '''
    cfg = QUERY_CONFIGS['zone_physical_flow']
    link = LINKS[key]
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
        yield _fetch(params, parse_zone_physical_flow, key)


def get_eic_code(key=None, start=None, function_filter: str = None, progress_callback=None) -> list:
    '''
        global registry download, not scoped to a zone/key — `key`/`start` accepted
        only so this matches sync.py's cursor fetch_fn(key, start, progress_callback) shape.
    '''
    if progress_callback:
        progress_callback("eic codes — downloading full registry")
    url = "https://eepublicdownloads.blob.core.windows.net/cio-lio/xml/allocated-eic-codes.xml"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return parse_eic_code(root, function_filter)
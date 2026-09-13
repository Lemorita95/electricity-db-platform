# https://eepublicdownloads.entsoe.eu/clean-documents/EDI/Library/EDI_best_practices_v1.pdf

import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from managers.config import QUERY_CONFIGS
from master.db.models import Price, Demand, ProductionResource, GeneratingUnit


def _text(elem: ET.Element) -> str:
    return elem.text if elem is not None else None
 
 
def _float(elem: ET.Element) -> float:
    return float(elem.text) if elem is not None and elem.text is not None else None


def parse_price(root: ET.Element, zone: str) -> list[Price]:
    cfg = QUERY_CONFIGS['price']
    ns = {'ns': cfg['namespace']}
    records = []

    for ts in root.findall('ns:TimeSeries', ns):
        period = ts.find('ns:Period', ns)
        resolution = period.find('ns:resolution', ns).text
        start = datetime.fromisoformat(period.find('ns:timeInterval/ns:start', ns).text.replace('Z', '+00:00'))
        currency = ts.find('ns:currency_Unit.name', ns).text
        interval = 15 if resolution == 'PT15M' else 60

        for point in period.findall('ns:Point', ns):
            pos = int(point.find('ns:position', ns).text)
            price = float(point.find('ns:price.amount', ns).text)
            timestamp = start + timedelta(minutes=interval * (pos - 1))

            records.append(Price(
                zone=zone,
                timestamp=timestamp,
                resolution=resolution,
                price=price,
                currency=currency,
            ))

    return records


def parse_demand(root: ET.Element, zone: str) -> list[Demand]:
    cfg = QUERY_CONFIGS['demand']
    ns = {'ns': cfg['namespace']}
    records = []

    for ts in root.findall('ns:TimeSeries', ns):
        for period in ts.findall('ns:Period', ns):  # loop all periods
            resolution = period.find('ns:resolution', ns).text
            start = datetime.fromisoformat(period.find('ns:timeInterval/ns:start', ns).text.replace('Z', '+00:00'))
            interval = 15 if resolution == 'PT15M' else 60

            for point in period.findall('ns:Point', ns):
                pos = int(point.find('ns:position', ns).text)
                quantity = float(point.find('ns:quantity', ns).text)
                timestamp = start + timedelta(minutes=interval * (pos - 1))

                records.append(Demand(
                    zone=zone,
                    timestamp=timestamp,
                    resolution=resolution,
                    quantity=quantity,
                    unit=cfg['unit']
                ))

    return records


def parse_generation_units(root: ET.Element, zone: str) -> list[ProductionResource]:
    cfg = QUERY_CONFIGS['generation_units']
    ns = {'ns': cfg['namespace']}

    records = []
    for ts in root.findall('ns:TimeSeries', ns):
        impl_date = date.fromisoformat(_text(ts.find('ns:implementation_DateAndOrTime.date', ns)))
        psr = ts.find('ns:MktPSRType', ns)

        units = [
            GeneratingUnit(
                unit_mrid=_text(gu.find('ns:mRID', ns)),
                name=_text(gu.find('ns:name', ns)),
                nominal_p_mw=_float(gu.find('ns:nominalP', ns)),
                psr_type=_text(gu.find('ns:generatingUnit_PSRType.psrType', ns)),
                location_name=_text(gu.find('ns:generatingUnit_Location.name', ns)),
                implementation_date=impl_date,
            )
            for gu in psr.findall('ns:GeneratingUnit_PowerSystemResources', ns)
        ]

        records.append(ProductionResource(
            resource_mrid=_text(ts.find('ns:registeredResource.mRID', ns)),
            resource_name=_text(ts.find('ns:registeredResource.name', ns)),
            location_name=_text(ts.find('ns:registeredResource.location.name', ns)),
            zone=zone,
            control_area_mrid=_text(ts.find('ns:ControlArea_Domain/ns:mRID', ns)),
            provider_mrid=_text(ts.find('ns:Provider_MarketParticipant/ns:mRID', ns)),
            business_type=_text(ts.find('ns:businessType', ns)),
            psr_type=_text(psr.find('ns:psrType', ns)),
            high_voltage_limit_kv=_float(psr.find('ns:production_PowerSystemResources.highVoltageLimit', ns)),
            nominal_p_mw=_float(psr.find('ns:nominalIP_PowerSystemResources.nominalP', ns)),
            implementation_date=impl_date,
            source_ts_mrid=_text(ts.find('ns:mRID', ns)),
            units=units,
        ))

    return records


def parse_eic_code(root: ET.Element, function_filter: str) -> list[dict]:
    ns = {'ns': 'urn:iec62325.351:tc57wg16:451-n:eicdocument:1:2'}
    records = []
    for eic_elem in root.findall('ns:EICCode_MarketDocument', ns):
        print(eic_elem.find('ns:mRID', ns).text)
        print(eic_elem.find('ns:long_Names.name', ns).text)
        
        function_names = eic_elem.findall("ns:Function_Names", ns)
        print([f.find("ns:name", ns).text for f in function_names])

    return records
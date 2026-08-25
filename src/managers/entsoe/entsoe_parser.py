import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from managers.config import QUERY_CONFIGS
from master.db.models import Price, Demand


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


def parse_eic_code(root: ET.Element, function_filter: str) -> list[dict]:
    ns = {'ns': 'urn:iec62325.351:tc57wg16:451-n:eicdocument:1:2'}
    records = []
    for eic_elem in root.findall('ns:EICCode_MarketDocument', ns):
        print(eic_elem.find('ns:mRID', ns).text)
        print(eic_elem.find('ns:long_Names.name', ns).text)
        
        function_names = eic_elem.findall("ns:Function_Names", ns)
        print([f.find("ns:name", ns).text for f in function_names])

    return records
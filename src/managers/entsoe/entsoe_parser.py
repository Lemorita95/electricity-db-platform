# https://eepublicdownloads.entsoe.eu/clean-documents/EDI/Library/EDI_best_practices_v1.pdf

import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from managers.config import QUERY_CONFIGS
from master.db.models import Price, Demand, ProductionResource, GeneratingUnit, \
    CrossBorderCapacity, ZonePhysicalFlow


def _text(elem: ET.Element) -> str:
    return elem.text if elem is not None else None
 
 
def _float(elem: ET.Element) -> float:
    return float(elem.text) if elem is not None and elem.text is not None else None


def _expand_points(points: list[ET.Element], ns: dict, start: datetime, step: timedelta, end: datetime, value_tag: str) -> list[tuple[datetime, float]]:
    '''
    Expands a Period's Points into one (timestamp, value) pair per resolution step.
    `value_tag` is the point's value element name (e.g. 'ns:price.amount', 'ns:quantity'),
    read from each source's QUERY_CONFIGS entry.

    Handles curveType A01 (every position present) and A03 (only positions where the
    value changes are present) transparently: each point's value is forward-filled from
    its own position up to (but not including) the next provided point's position, and
    the last point's value is forward-filled through `end`. For A01, the "next position"
    is always the current position + 1, so this degenerates to one point per step with
    no actual filling — same result as a direct 1:1 parse.

    Not valid for A02/A04/A05 (independent readings / breakpoint ramps) — none of the
    business processes we parse today declare those curveTypes.
    '''
    expanded = []
    for i, point in enumerate(points):
        pos = int(point.find('ns:position', ns).text)
        value = float(point.find(value_tag, ns).text)
        block_start = start + step * (pos - 1)

        if i + 1 < len(points):
            next_pos = int(points[i + 1].find('ns:position', ns).text)
            block_end = start + step * (next_pos - 1)
        else:
            block_end = end

        t = block_start
        while t < block_end:
            expanded.append((t, value))
            t += step

    return expanded


def parse_price(root: ET.Element, zone: str) -> list[Price]:
    cfg = QUERY_CONFIGS['price']
    ns = {'ns': cfg['namespace']}
    records = []

    for ts in root.findall('ns:TimeSeries', ns):
        period = ts.find('ns:Period', ns)
        resolution = period.find('ns:resolution', ns).text
        start = datetime.fromisoformat(period.find('ns:timeInterval/ns:start', ns).text.replace('Z', '+00:00'))
        end = datetime.fromisoformat(period.find('ns:timeInterval/ns:end', ns).text.replace('Z', '+00:00'))
        currency = ts.find('ns:currency_Unit.name', ns).text
        step = timedelta(minutes=15 if resolution == 'PT15M' else 60)

        points = period.findall('ns:Point', ns)
        for timestamp, price in _expand_points(points, ns, start, step, end, cfg['value_tag']):
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
            end = datetime.fromisoformat(period.find('ns:timeInterval/ns:end', ns).text.replace('Z', '+00:00'))
            step = timedelta(minutes=15 if resolution == 'PT15M' else 60)

            points = period.findall('ns:Point', ns)
            for timestamp, quantity in _expand_points(points, ns, start, step, end, cfg['value_tag']):
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


def parse_cross_border_capacity(root: ET.Element, zone: str) -> list[CrossBorderCapacity]:
    cfg = QUERY_CONFIGS['cross_border_capacity']
    ns = {'ns': cfg['namespace']}
    records = []

    for ts in root.findall('ns:TimeSeries', ns):
        flow_destination = _text(ts.find('ns:in_Domain.mRID', ns))
        flow_origin = _text(ts.find('ns:out_Domain.mRID', ns))
        unit = _text(ts.find('ns:quantity_Measure_Unit.name', ns))

        for period in ts.findall('ns:Period', ns):
            resolution = period.find('ns:resolution', ns).text
            start = datetime.fromisoformat(period.find('ns:timeInterval/ns:start', ns).text.replace('Z', '+00:00'))
            end = datetime.fromisoformat(period.find('ns:timeInterval/ns:end', ns).text.replace('Z', '+00:00'))
            step = timedelta(minutes=15 if resolution == 'PT15M' else 60)

            points = period.findall('ns:Point', ns)
            for timestamp, quantity in _expand_points(points, ns, start, step, end, cfg['value_tag']):
                records.append(CrossBorderCapacity(
                    zone=zone,
                    flow_destination=flow_destination,
                    flow_origin=flow_origin,
                    timestamp=timestamp,
                    resolution=resolution,
                    quantity=quantity,
                    unit=unit,
                ))

    return records


def parse_zone_physical_flows(root: ET.Element, zone: str) -> list[ZonePhysicalFlow]:
    cfg = QUERY_CONFIGS['zone_physical_flows']
    ns = {'ns': cfg['namespace']}
    records = []

    for ts in root.findall('ns:TimeSeries', ns):
        flow_destination = _text(ts.find('ns:in_Domain.mRID', ns))
        flow_origin = _text(ts.find('ns:out_Domain.mRID', ns))
        unit = _text(ts.find('ns:quantity_Measure_Unit.name', ns))

        for period in ts.findall('ns:Period', ns):
            resolution = period.find('ns:resolution', ns).text
            start = datetime.fromisoformat(period.find('ns:timeInterval/ns:start', ns).text.replace('Z', '+00:00'))
            end = datetime.fromisoformat(period.find('ns:timeInterval/ns:end', ns).text.replace('Z', '+00:00'))
            step = timedelta(minutes=15 if resolution == 'PT15M' else 60)

            points = period.findall('ns:Point', ns)
            for timestamp, quantity in _expand_points(points, ns, start, step, end, cfg['value_tag']):
                records.append(ZonePhysicalFlow(
                    zone=zone,
                    flow_destination=flow_destination,
                    flow_origin=flow_origin,
                    timestamp=timestamp,
                    resolution=resolution,
                    quantity=quantity,
                    unit=unit,
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
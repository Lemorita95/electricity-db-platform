"""
Basic tests for src/managers/entsoe/* — confirms the normal case works
for each of the three request shapes (plain, load, link-based), not
every edge case. No network calls.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from unittest import mock

import pytest
import requests

from managers.entsoe.entsoe_client import EntsoClient
from managers.entsoe import entsoe_endpoints as ee
from managers.entsoe import entsoe_parser as ep
from managers.config import NORDICS_CODES, LINKS, EIC_CODES, QUERY_CONFIGS

NS = "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"

PRICE_XML = f"""<Publication_MarketDocument xmlns="{NS}">
  <TimeSeries>
    <currency_Unit.name>EUR</currency_Unit.name>
    <Period>
      <timeInterval><start>2025-06-10T00:00Z</start><end>2025-06-10T02:00Z</end></timeInterval>
      <resolution>PT60M</resolution>
      <Point><position>1</position><price.amount>45.32</price.amount></Point>
      <Point><position>2</position><price.amount>50.10</price.amount></Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>"""

GEN_UNITS_XML = """<Configuration_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-6:configurationdocument:3:0">
  <TimeSeries>
    <implementation_DateAndOrTime.date>2025-01-01</implementation_DateAndOrTime.date>
    <registeredResource.mRID>17W100000000TEST</registeredResource.mRID>
    <registeredResource.name>Test Plant</registeredResource.name>
    <MktPSRType>
      <psrType>B14</psrType>
      <production_PowerSystemResources.highVoltageLimit>400</production_PowerSystemResources.highVoltageLimit>
      <nominalIP_PowerSystemResources.nominalP>600</nominalIP_PowerSystemResources.nominalP>
      <GeneratingUnit_PowerSystemResources>
        <mRID>17W100000000UN01</mRID>
        <name>Unit 1</name>
        <nominalP>300</nominalP>
      </GeneratingUnit_PowerSystemResources>
    </MktPSRType>
  </TimeSeries>
</Configuration_MarketDocument>"""


def test_parse_price_returns_a_row_per_point():
    records = ep.parse_price(ET.fromstring(PRICE_XML), "SE3")
    assert [r.price for r in records] == [45.32, 50.10]
    assert records[0].zone == "SE3"


def test_parse_price_handles_pt30m_resolution():
    # regression: resolution handling used to special-case only PT15M and
    # treat everything else as 60 minutes, which mis-spaced timestamps and
    # silently dropped the last point of a PT30M series.
    xml = f"""<Publication_MarketDocument xmlns="{NS}">
      <TimeSeries>
        <currency_Unit.name>EUR</currency_Unit.name>
        <Period>
          <timeInterval><start>2025-06-10T00:00Z</start><end>2025-06-10T01:30Z</end></timeInterval>
          <resolution>PT30M</resolution>
          <Point><position>1</position><price.amount>10</price.amount></Point>
          <Point><position>2</position><price.amount>20</price.amount></Point>
          <Point><position>3</position><price.amount>30</price.amount></Point>
        </Period>
      </TimeSeries>
    </Publication_MarketDocument>"""
    records = ep.parse_price(ET.fromstring(xml), "SE3")
    assert [r.price for r in records] == [10.0, 20.0, 30.0]
    assert [r.timestamp.minute for r in records] == [0, 30, 0]


def test_parse_generation_units_nests_units_under_the_plant():
    records = ep.parse_generation_units(ET.fromstring(GEN_UNITS_XML), "SE3")
    assert len(records) == 1
    assert records[0].resource_name == "Test Plant"
    assert len(records[0].units) == 1
    assert records[0].units[0].unit_mrid == "17W100000000UN01"


def test_get_price_builds_expected_params():
    captured = {}

    def fake_get(params):
        captured.update(params)
        return ET.fromstring(f'<Publication_MarketDocument xmlns="{NS}"/>')

    with mock.patch.object(ee.entsoe_client, "get", side_effect=fake_get):
        ee.get_price("SE3", datetime(2025, 6, 1), datetime(2025, 6, 2))

    assert captured["documentType"] == QUERY_CONFIGS["price"]["documentType"]
    assert captured["in_Domain"] == NORDICS_CODES["SE3"]["eic"]
    assert captured["periodStart"] == "202506010000"


def test_get_zone_physical_flow_swaps_domains_by_link_direction():
    key = "DK1-SE3"
    assert key in LINKS, "adjust key if config changes"
    link = LINKS[key]
    captured = {}

    def fake_get(params):
        captured.update(params)
        return ET.fromstring(
            '<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:'
            'publicationdocument:7:0"/>'
        )

    with mock.patch.object(ee.entsoe_client, "get", side_effect=fake_get):
        ee.get_zone_physical_flow(key, datetime(2025, 6, 1), datetime(2025, 6, 2))

    assert captured["in_Domain"] == EIC_CODES[link["destination"]]["eic"]
    assert captured["out_Domain"] == EIC_CODES[link["origin"]]["eic"]


def test_client_returns_parsed_xml_on_success():
    client = EntsoClient()
    resp = mock.Mock(spec=requests.Response, status_code=200, content=b"<ok/>")
    resp.raise_for_status.return_value = None
    with mock.patch.object(client.session, "get", return_value=resp):
        root = client.get({"documentType": "A44"})
    assert root.tag == "ok"


def test_client_raises_on_error_response():
    client = EntsoClient()
    resp = mock.Mock(spec=requests.Response, status_code=400)
    resp.raise_for_status.side_effect = requests.HTTPError("bad request")
    with mock.patch.object(client.session, "get", return_value=resp):
        with pytest.raises(requests.HTTPError):
            client.get({"documentType": "A44"})

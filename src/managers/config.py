import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # project root
load_dotenv(BASE_DIR / ".env")

ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
ENTSOE_BASE_URL = os.getenv("ENTSOE_BASE_URL")

EUMDAC_CONSUMER_KEY = os.getenv("EUMDAC_CONSUMER_KEY")
EUMDAC_CONSUMER_SECRET = os.getenv("EUMDAC_CONSUMER_SECRET")

CDS_API_URL = os.getenv("CDS_API_URL")
CDS_API_KEY = os.getenv("CDS_API_KEY")

# ''' API QUERY PARAMETERS '''
EIC_CODES: dict[str, dict] = {
    'SE1':      {'eic': '10Y1001A1001A44P', 'lat': 65.58,   'lon': 22.15},  # Luleå
    'SE2':      {'eic': '10Y1001A1001A45N', 'lat': 62.39,   'lon': 17.31},  # Sundsvall
    'SE3':      {'eic': '10Y1001A1001A46L', 'lat': 59.33,   'lon': 18.07},  # Stockholm
    'SE4':      {'eic': '10Y1001A1001A47J', 'lat': 55.60,   'lon': 13.00},  # Malmö
    'DK1':      {'eic': '10YDK-1--------W', 'lat': 56.16,   'lon': 10.20},  # Aarhus
    'DK2':      {'eic': '10YDK-2--------M', 'lat': 55.68,   'lon': 12.57},  # Copenhagen
    'FI':       {'eic': '10YFI-1--------U', 'lat': 60.17,   'lon': 24.94},  # Helsinki
    'NO1':      {'eic': '10YNO-1--------2', 'lat': 59.91,   'lon': 10.75},  # Oslo
    'NO2':      {'eic': '10YNO-2--------T', 'lat': 58.15,   'lon':  7.99},  # Kristiansand
    'NO3':      {'eic': '10YNO-3--------J', 'lat': 63.43,   'lon': 10.39},  # Trondheim
    'NO4':      {'eic': '10YNO-4--------9', 'lat': 69.65,   'lon': 18.96},  # Tromsø
    'NO5':      {'eic': '10Y1001A1001A48H', 'lat': 60.39,   'lon':  5.33},  # Bergen
    'NL':       {'eic': '10YNL----------L', 'lat': None,    'lon': None},
    'GB':       {'eic': '10YGB----------A', 'lat': None,    'lon': None},
    'DK1A':     {'eic': '10YDK-1-------AA', 'lat': None,    'lon': None},
    'DE-LU':    {'eic': '10Y1001A1001A82H', 'lat': None,    'lon': None},
    'DE-AT-LU': {'eic': '10Y1001A1001A63L', 'lat': None,    'lon': None},
    'LT':       {'eic': '10YLT-1001A0008Q', 'lat': None,    'lon': None},
    'PL':       {'eic': '10YPL-AREA-----S', 'lat': None,    'lon': None},
    'SE3A':     {'eic': '10Y1001C--00148Q', 'lat': None,    'lon': None},
    'DK1-NO1':  {'eic': '46Y000000000007M', 'lat': None,    'lon': None},
    'RU':       {'eic': '10Y1001A1001A49F', 'lat': None,    'lon': None},
    'EE':       {'eic': '10Y1001A1001A39I', 'lat': None,    'lon': None},
    'NO2A':     {'eic': '10Y1001C--001219', 'lat': None,    'lon': None},
    'NO1A':     {'eic': '10Y1001A1001A64J', 'lat': None,    'lon': None},
}

NORDICS_CODES: dict[str, dict] = {
    k: v for k, v in EIC_CODES.items() if k in ['SE1', 'SE2', 'SE3', 'SE4', 'DK1', 'DK2', 'FI', 'NO1', 'NO2', 'NO3', 'NO4', 'NO5']
}

connections = {
    'DK1': ['DE-AT-LU', 'DE-LU', 'DK1A', 'DK2', 'GB', 'NL', 'NO2', 'SE3'],
    'DK2': ['DE-AT-LU', 'DE-LU', 'DK1', 'NL', 'SE4'],
    'NO1': ['NO1A', 'NO2', 'NO3', 'NO5', 'SE3'],
    'NO2': ['DE-LU', 'DK1', 'GB', 'NL', 'NO1', 'NO2A', 'NO5'],
    'NO3': ['NO1', 'NO4', 'NO5', 'SE2'],
    'NO4': ['FI', 'NO3', 'SE1', 'SE2'],
    'NO5': ['NO1', 'NO2', 'NO3'],
    'SE1': ['FI', 'NO4', 'SE2'],
    'SE2': ['NO3', 'NO4', 'SE1', 'SE3'],
    'SE3': ['DK1', 'DK1-NO1', 'FI', 'NO1', 'SE2', 'SE3A', 'SE4'],
    'SE4': ['DE-AT-LU', 'DE-LU', 'DK2', 'LT', 'PL', 'SE3'],
    'FI':  ['EE', 'NO4', 'RU', 'SE1', 'SE3']
 }

def build_links_with_reciprocity(connections: dict[str, list]):
    # build known links
    exists = set()
    for origin, destinations in connections.items():
        for destination in destinations:
            exists.add((origin, destination))

    # check for reciprocity
    missing = set()
    for origin, destination in exists:
        reverse = (destination, origin)

        if reverse not in exists:
            missing.add(reverse)

    # unite sets and build all links
    links = {f'{origin}-{destination}': {'origin': origin, 'destination': destination} for origin, destination in exists | missing}
    
    return links


LINKS: dict[str, dict] = build_links_with_reciprocity(connections=connections)


QUERY_CONFIGS = {
    'price': {
        'documentType': 'A44',
        'contract_MarketAgreement.type': 'A01',
        'namespace': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3',
        'value_tag': 'ns:price.amount',
    },
    'demand': {
        'documentType': 'A65',
        'processType': 'A16',
        'namespace': 'urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0',
        'value_tag': 'ns:quantity',
        'unit': 'MAW',
    },
    'generation_units': {
        'documentType': 'A95',
        'businessType': 'B11',
        'namespace': 'urn:iec62325.351:tc57wg16:451-6:configurationdocument:3:0',
    },
    'cross_border_capacity': {
        'documentType': 'A93',
        'namespace': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0',
        'curveType': 'A03',
        'value_tag': 'ns:quantity',
    },
    'zone_physical_flows': {
    'documentType': 'A11',
    'namespace': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0',
    'curveType': 'A03',
    'value_tag': 'ns:quantity',
    },
    'eumet': {
        'collectionID': 'EO:EUM:DAT:0863',
        'sat': 'MSG',
        'compositeType': 'PT30M',
        'statisticType': "None",
        'unit': 'W_m2',
        'var_type': ['SID', 'SIS']
    },
    'copernicus': {
        'dataset': "reanalysis-era5-single-levels-timeseries",
        'request': {
            "variable": [
                "total_sky_direct_solar_radiation_at_surface",
                "surface_solar_radiation_downwards",
                "2m_temperature",
                "10m_u_component_of_wind",
                "10m_v_component_of_wind"
            ],
            "data_format": "csv",
        }
    },
}
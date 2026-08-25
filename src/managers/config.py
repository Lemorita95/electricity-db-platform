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
EIC_CODES = {
    'SE1': {'eic': '10Y1001A1001A44P', 'lat': 65.58, 'lon': 22.15},  # Luleå
    'SE2': {'eic': '10Y1001A1001A45N', 'lat': 62.39, 'lon': 17.31},  # Sundsvall
    'SE3': {'eic': '10Y1001A1001A46L', 'lat': 59.33, 'lon': 18.07},  # Stockholm
    'SE4': {'eic': '10Y1001A1001A47J', 'lat': 55.60, 'lon': 13.00},  # Malmö
    'DK1': {'eic': '10YDK-1--------W', 'lat': 56.16, 'lon': 10.20},  # Aarhus
    'DK2': {'eic': '10YDK-2--------M', 'lat': 55.68, 'lon': 12.57},  # Copenhagen
    'FI':  {'eic': '10YFI-1--------U', 'lat': 60.17, 'lon': 24.94},  # Helsinki
    'NO1': {'eic': '10YNO-1--------2', 'lat': 59.91, 'lon': 10.75},  # Oslo
    'NO2': {'eic': '10YNO-2--------T', 'lat': 58.15, 'lon':  7.99},  # Kristiansand
    'NO3': {'eic': '10YNO-3--------J', 'lat': 63.43, 'lon': 10.39},  # Trondheim
    'NO4': {'eic': '10YNO-4--------9', 'lat': 69.65, 'lon': 18.96},  # Tromsø
    'NO5': {'eic': '10Y1001A1001A48H', 'lat': 60.39, 'lon':  5.33},  # Bergen
}

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
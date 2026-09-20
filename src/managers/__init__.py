from managers.entsoe.entsoe_client import EntsoClient
from managers.entsoe.entsoe_endpoints import entsoe_client, get_price, get_demand, get_generation_units, \
    get_cross_border_capacity, get_zone_physical_flows, get_eic_code
# from managers.entsoe.entsoe_parser import parse_price, parse_demand, parse_generation_units, parse_eic_code

from managers.copernicus.copernicus_client import CopernicusClient
from managers.copernicus.copernicus_endpoints import get_era5, copernicus_client
# from managers.copernicus.copernicus_parser import parse_weather

from managers.eumet.eumet_client import EumetClient
from managers.eumet.eumet_endpoints import get_sarah3, eumet_client
# from managers.eumet.eumet_parser import parse_irradiance
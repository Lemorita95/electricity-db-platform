from managers.entsoe.entsoe_client import EntsoClient
from managers.entsoe.entsoe_endpoints import get_entsoe_client, get_price, get_demand, get_generation_units, \
    get_cross_border_capacity, get_zone_physical_flow, get_eic_code, get_generation, get_wind_solar_forecast, \
    get_load_forecast, get_hydro_reservoir
# from managers.entsoe.entsoe_parser import parse_price, parse_demand, parse_generation_units, parse_eic_code

from managers.copernicus.copernicus_client import CopernicusClient
from managers.copernicus.copernicus_endpoints import get_era5, get_copernicus_client
# from managers.copernicus.copernicus_parser import parse_weather

from managers.eumet.eumet_client import EumetClient
from managers.eumet.eumet_endpoints import get_sarah3, get_eumet_client
# from managers.eumet.eumet_parser import parse_irradiance

from managers.jao.jao_client import JaoClient, JaoRejected
from managers.jao.jao_endpoints import get_binding_cnecs, get_jao_client
# from managers.jao.jao_parser import parse_binding_cnecs
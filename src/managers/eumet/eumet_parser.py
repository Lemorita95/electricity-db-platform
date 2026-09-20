import io
import os
import zipfile
import tempfile
import xarray as xr

from managers.config import NORDICS_CODES, QUERY_CONFIGS
from master.db.models import Irradiance


def get_value(arr, i):
    if arr is None:
        return None
    val = arr[i]
    return None if val is None else float(val)


def parse_irradiance(product, zone: str, var_type: str) -> list[Irradiance]:
    cfg = QUERY_CONFIGS['irradiance']
    lat = NORDICS_CODES[zone]['lat']
    lon = NORDICS_CODES[zone]['lon']
    records = []

    with product.open() as raw:
        buf = io.BytesIO(raw.read())

    with zipfile.ZipFile(buf) as z:
        nc_name  = next(n for n in z.namelist() if n.endswith(".nc"))
        nc_bytes = z.read(nc_name)

    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        tmp.write(nc_bytes)
        tmp_path = tmp.name

    try:
        with xr.open_dataset(tmp_path, engine="netcdf4") as ds:
            if var_type not in ds.data_vars:
                return []
            extracted = {var_type.lower(): ds[var_type].sel(lat=lat, lon=lon, method="nearest").values}
            timestamps = ds.coords["time"].values if "time" in ds.coords else [None]
            sis = extracted.get("sis")
            sid = extracted.get("sid")
            for i in range(len(timestamps)):
                timestamp = (
                    timestamps[i].astype("datetime64[ms]").astype("O")
                    if timestamps[i] is not None else None
                )
                records.append(
                    Irradiance(
                        zone=zone,
                        timestamp=timestamp,
                        resolution=cfg["compositeType"],
                        sis=get_value(sis, i),
                        sid=get_value(sid, i),
                        unit=cfg["unit"],
                    )
                )
    finally:
        os.unlink(tmp_path)

    return records
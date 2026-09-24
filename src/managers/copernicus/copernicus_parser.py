import csv
import os
import tempfile
import zipfile
from datetime import datetime

from managers.config import QUERY_CONFIGS
from master.db.models import Weather


def _float_or_none(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_time(value: str) -> datetime:
    if not value:
         return None
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    return datetime.fromisoformat(value)


def parse_weather(results, zone: str) -> list[Weather]:
    cfg = QUERY_CONFIGS['copernicus']
    records = []

    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        results.download(tmp_path)
        
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            csv_file = next(f for f in zip_ref.namelist() if f.endswith('.csv'))
            with zip_ref.open(csv_file) as fh:
                reader = csv.DictReader(line.decode('utf-8') for line in fh)
                for row in reader:
                    timestamp = _parse_time(row.get('valid_time'))
                    if timestamp is None:
                        continue

                    records.append(
                        Weather(
                            zone=zone,
                            timestamp=timestamp,
                            resolution=cfg.get('resolution', 'PT1H'),
                            fdir=_float_or_none(row.get('fdir')),
                            ssrd=_float_or_none(row.get('ssrd')),
                            temperature_2m=_float_or_none(row.get('t2m')),
                            wind_u_10m=_float_or_none(row.get('u10')),
                            wind_v_10m=_float_or_none(row.get('v10')),
                        )
                    )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return records

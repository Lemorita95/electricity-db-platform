import json
from datetime import date, datetime, time, timedelta, timezone
from functools import cache
from typing import Iterator
from zoneinfo import ZoneInfo

from master.db.models import BindingCnec, FbBorderFlow, FbNetPosition

from managers.config import QUERY_CONFIGS
from managers.jao.jao_client import JaoClient
from managers.jao.jao_parser import parse_binding_cnecs, parse_fb_monitoring
from managers.chunks import chunk_by_period


@cache
def get_jao_client() -> JaoClient:
    return JaoClient()


MARKET_TZ = ZoneInfo('Europe/Stockholm')
READINESS_DAYS = 2  # business days older than this are past publication


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def _as_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _business_day(dt: datetime) -> date:
    return dt.astimezone(MARKET_TZ).date()


def _publication_status(day: date, cfg: dict) -> str:
    day_start = datetime.combine(day, time(), MARKET_TZ)
    day_end = datetime.combine(day + timedelta(days=1), time(), MARKET_TZ)
    body = get_jao_client().monitoring(_iso_utc(day_start), _iso_utc(day_end))
    for entry in body.get('data') or []:
        if entry.get('fileType') == cfg['monitoring_file_type']:
            return entry.get('status', 'unknown')
    return 'unknown'


def _hourly(cfg_name: str, parse_fn, key: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list]:
    '''
        one request and one yielded batch per hour of the cfg's dataset and filter.
        recent business days are only requested once JAO's monitoring reports them as Received.
    '''
    cfg = QUERY_CONFIGS[cfg_name]
    start = _as_utc(start).replace(minute=0, second=0, microsecond=0)
    end = _as_utc(end)
    windows = chunk_by_period(start, end, '1h')
    first_checked_day = _business_day(_utc_now()) - timedelta(days=READINESS_DAYS)
    ready_days = set()

    for i, (window_start, window_end) in enumerate(windows, 1):
        day = _business_day(window_start)
        if day >= first_checked_day and day not in ready_days:
            status = _publication_status(day, cfg)
            if status != 'Received':
                if progress_callback:
                    progress_callback(f"JAO: {day.isoformat()} {status}, stopping")
                return
            ready_days.add(day)

        if progress_callback:
            progress_callback(f"jao {window_start.strftime('%Y-%m-%d %H:%M')} ({i}/{len(windows)})")

        params = {
            'FromUtc': _iso_utc(window_start),
            'ToUtc': _iso_utc(window_end),
            'Filter': json.dumps(cfg['filter']),
            'Take': cfg['take'],
        }
        body = get_jao_client().get(cfg['dataset'], params)
        rows = body.get('data') or []
        total = body.get('totalRowsWithFilter', len(rows))
        if total > len(rows):
            raise ValueError(
                f"JAO returned {len(rows)} of {total} rows for {params['FromUtc']}, raise 'take' instead of paging"
            )

        yield parse_fn(rows, key)


def get_binding_cnecs(key: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[BindingCnec]]:
    '''binding CNECs for a single 'key' ('NORDIC'), one batch per hour'''
    yield from _hourly('jao_binding_cnec', parse_binding_cnecs, key, start, end, progress_callback)


def get_fb_monitoring(key: str, start: datetime, end: datetime, progress_callback=None) -> Iterator[list[FbBorderFlow | FbNetPosition]]:
    '''
        border flows and net positions for a single 'key' ('NORDIC'), one request and one mixed batch per hour;
        sync's upsert_by_model saves each record to its own table
    '''
    yield from _hourly('jao_fb_monitoring', parse_fb_monitoring, key, start, end, progress_callback)

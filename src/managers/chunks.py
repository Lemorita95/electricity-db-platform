from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re


display = lambda s: s.strftime('%d/%m/%Y') if isinstance(s, datetime) else s


def parse_chunk_size(chunk_str: str):
    match = re.fullmatch(r'(\d+)(d|w|m|y)', chunk_str.lower())
    if not match:
        raise ValueError(f"Invalid chunk size '{chunk_str}'. Use format like '30d', '2w', '3m', '1y'")
    value, unit = int(match.group(1)), match.group(2)
    return {
        'd': timedelta(days=value),
        'w': timedelta(weeks=value),
        'm': relativedelta(months=value),
        'y': relativedelta(years=value),
    }[unit]


def chunk_by_period(start: datetime, end: datetime, chunk_size: str = '30d'):
    delta = parse_chunk_size(chunk_size)
    chunks = []
    current = start
    while current < end:
        next_chunk = min(current + delta, end)
        chunks.append((current, next_chunk))
        current = next_chunk
    return chunks
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timedelta

from master.db.models import Price, Demand, Weather

BATCH_SIZE = 1000

CONSTRAINTS = {
    Price: 'uq_price_zone_timestamp',
    Demand: 'uq_demand_zone_timestamp',
    Weather: 'uq_weather_zone_timestamp',
}

RESOLUTION_MAP = {
    "PT15M": timedelta(minutes=15),
    "PT30M": timedelta(minutes=30),
    "PT60M": timedelta(hours=1),
    "PT1H": timedelta(hours=1),
}


def _build_conflict_update(stmt, columns: set) -> dict:
    return {
        column: getattr(stmt.excluded, column)
        for column in columns
        if column not in {'zone', 'timestamp'}
    }


def upsert(session: Session, model, records: list) -> None:
    if not records:
        return
    
    # remove duplicates
    seen = {}
    for r in records:
        seen[(r.zone, r.timestamp)] = r
    records = list(seen.values())

    rows = [r.model_dump(exclude={'id'}) for r in records]
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        all_columns = set().union(*(row.keys() for row in chunk))
        stmt = insert(model).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint=CONSTRAINTS[model],
            set_=_build_conflict_update(stmt, all_columns)
        )
        session.exec(stmt)
    session.commit()


def fetch(session: Session, model, zone: str, start: datetime, end: datetime):
    statement = select(model).where(
        model.zone == zone,
        model.timestamp >= start,
        model.timestamp <= end,
    ).order_by(model.timestamp)
    return session.exec(statement).all()


def _build_missing_ranges(start, end, rows):
    if not rows:
        return [{"start": start, "end": end}]

    gaps = []

    # Leading gap
    first_ts, _ = rows[0]
    if first_ts > start:
        gaps.append({
            "start": start,
            "end": first_ts,
        })

    # Middle gaps
    for (current_ts, current_res), (next_ts, _) in zip(rows, rows[1:]):
        expected_next = current_ts + RESOLUTION_MAP[current_res]

        if next_ts > expected_next:
            gaps.append({
                "start": expected_next,
                "end": next_ts,
            })

    # Trailing gap
    last_ts, last_res = rows[-1]
    last_expected = last_ts + RESOLUTION_MAP[last_res]

    if last_expected < end:
        gaps.append({
            "start": last_expected,
            "end": end,
        })

    return gaps


def get_timestamps(session: Session, model, zone: str, start: datetime, end: datetime) -> dict:
    statement = select(model.timestamp, model.resolution).where(
        model.zone == zone,
        model.timestamp >= start,
        model.timestamp <= end,
    ).order_by(model.timestamp)
    rows = session.exec(statement).all()
    return {
        'zone': zone,
        'start': start,
        'end': end,
        'existing_timestamps': [row[0] for row in rows],
        'missing_ranges': _build_missing_ranges(start, end, rows),
    }
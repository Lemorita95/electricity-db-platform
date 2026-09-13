from sqlmodel import Session, select
from sqlalchemy import UniqueConstraint, func, and_, inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert
from datetime import date, datetime, timedelta


BATCH_SIZE = 1000


RESOLUTION_MAP = {
    "PT15M": timedelta(minutes=15),
    "PT30M": timedelta(minutes=30),
    "PT60M": timedelta(hours=1),
    "PT1H": timedelta(hours=1),
}


def _get_unique_constraint(model) -> UniqueConstraint:
    constraints = [c for c in model.__table__.constraints if isinstance(c, UniqueConstraint)]
    if len(constraints) != 1:
        raise ValueError(f"{model.__name__} needs exactly one UniqueConstraint")
    return constraints[0]


''' queries for date range data (e.g. start -> end) '''


def _build_conflict_update(stmt, columns: set, key_columns: set) -> dict:
    return {
        column: getattr(stmt.excluded, column)
        for column in columns
        if column not in key_columns
    }


def upsert_timeseries(session: Session, model, records: list) -> None:
    if not records:
        return
    constraint = _get_unique_constraint(model)
    key_columns = sorted(constraint.columns.keys())
    
    # remove duplicates
    seen = {}
    for r in records:
        seen[tuple(getattr(r, c) for c in key_columns)] = r
    records = list(seen.values())

    rows = [r.model_dump(exclude={'id'}) for r in records]
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        all_columns = set().union(*(row.keys() for row in chunk))
        stmt = insert(model).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint=constraint.name,
            set_=_build_conflict_update(stmt, all_columns, set(key_columns))
        )
        session.exec(stmt)
    session.commit()


def fetch_timeseries(session: Session, model, zone: str, start: datetime, end: datetime):
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


''' queries for single date data (e.g. no start-end) '''

def _get_child_relationship(model):
    '''
        used to avoid hardcoding the child`s attributes.
    '''
    relationships = list(inspect(model).relationships)
    if len(relationships) != 1:
        raise ValueError(f"{model.__name__} needs exactly one relationship for upsert_graph")
    rel = relationships[0]
    _, remote_col = rel.local_remote_pairs[0]
    return rel.key, rel.mapper.class_, remote_col.name  # ('units', GeneratingUnit, 'resource_id')


def upsert_graph(session: Session, model, records: list) -> None:
    if not records:
        return
    constraint = _get_unique_constraint(model) # get parent contraints from UniqueContraints
    key_columns = list(constraint.columns.keys()) # flat into their columns
    rel_name, child_model, fk_attr = _get_child_relationship(model) # get parent-child relationships and foreign key

    rows = [r.model_dump(exclude={'id', rel_name}) for r in records]
    stmt = insert(model).values(rows)
    # .returning() for rows actually written
    stmt = stmt.on_conflict_do_nothing(constraint=constraint.name).returning(model.id, *[getattr(model, c) for c in key_columns])
    inserted = {tuple(row[1:]): row[0] for row in session.exec(stmt).all()} 

    all_children = []
    for r in records:
        key = tuple(getattr(r, c) for c in key_columns)
        if key not in inserted:
            continue
        for child in getattr(r, rel_name): # avoid explicitly name the relashionship
            setattr(child, fk_attr, inserted[key]) # avoid explicitly name the key
            all_children.append(child)

    if all_children:
        child_constraint = _get_unique_constraint(child_model)
        child_rows = [c.model_dump(exclude={'id'}) for c in all_children]
        child_stmt = insert(child_model).values(child_rows).on_conflict_do_nothing(constraint=child_constraint.name)
        session.exec(child_stmt)

    session.commit()


def fetch_graph(session: Session, model, zone: str, as_of: date):
    '''
    note date column naming convention
    '''
    constraint = _get_unique_constraint(model)
    key_columns = [c for c in constraint.columns.keys() if c != 'implementation_date']
    rel_name, _, _ = _get_child_relationship(model)

    subq = (
        select(*[getattr(model, c) for c in key_columns], func.max(model.implementation_date).label('max_date'))
        .where(model.zone == zone, model.implementation_date <= as_of)
        .group_by(*[getattr(model, c) for c in key_columns])
        .subquery()
    )
    join_conditions = [getattr(model, c) == getattr(subq.c, c) for c in key_columns] + \
                       [model.implementation_date == subq.c.max_date]

    stmt = select(model).join(subq, and_(*join_conditions)).options(selectinload(getattr(model, rel_name)))
    return session.exec(stmt).all()
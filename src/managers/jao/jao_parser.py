from datetime import datetime, timezone, timedelta

from master.db.models import BindingCnec, CnecPtdf, FbBorderFlow, FbNetPosition


PTDF_PREFIX = 'ptdf_'
SDAC_15MIN_GO_LIVE = datetime(2025, 9, 30, 22, tzinfo=timezone.utc)


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _resolution(timestamps: set[datetime]) -> str:
    '''
    15 min spacing between the payload's timestamps means PT15M; a single timestamp
    (or wider spacing, when a quarter has no binding CNEC) falls back to the SDAC go-live
    '''
    ordered = sorted(timestamps)
    if any(b - a == timedelta(minutes=15) for a, b in zip(ordered, ordered[1:])):
        return 'PT15M'
    return 'PT15M' if ordered[0] >= SDAC_15MIN_GO_LIVE else 'PT60M'


def parse_binding_cnecs(rows: list[dict], key: str) -> list[BindingCnec]:
    if not rows:
        return []

    timestamps = {_parse_utc(row['dateTimeUtc']) for row in rows}
    resolution = _resolution(timestamps)

    records = []
    seen = set()
    for row in rows:
        timestamp = _parse_utc(row['dateTimeUtc'])
        row_key = (timestamp, row['mrId'], row['cnecName'])
        if row_key in seen:
            raise ValueError(f"duplicate CNEC {row['mrId']} / {row['cnecName']} at {timestamp.isoformat()}")
        seen.add(row_key)

        records.append(
            BindingCnec(
                zone=key,
                timestamp=timestamp,
                resolution=resolution,
                mr_id=row['mrId'],
                cnec_name=row['cnecName'],
                cnec_type=row.get('cnecType'),
                tso=row.get('tso'),
                bidding_zone_from=row.get('biddingZoneFrom'),
                bidding_zone_to=row.get('biddingZoneTo'),
                cne_name=row.get('cneName'),
                cont_name=row.get('contName'),
                ram=row.get('ram'),
                fmax=row.get('fmax'),
                fref=row.get('fref'),
                flow_fb=row.get('flowFb'),
                shadow_price=row['shadowPrice'],
                last_modified_on=_parse_utc(row.get('lastModifiedOn')),
                ptdfs=[
                    CnecPtdf(bidding_zone=field[len(PTDF_PREFIX):], ptdf=value)
                    for field, value in row.items()
                    if field.startswith(PTDF_PREFIX)
                ],
            )
        )
    return records


def _system_rows(rows: list[dict], prefix: str) -> list[dict]:
    '''rows whose cnecName starts with prefix; JAO writes both NetPosition_ and Netposition_'''
    return [row for row in rows if row['cnecName'].lower().startswith(prefix.lower())]


def parse_fb_border_flows(rows: list[dict], key: str) -> list[FbBorderFlow]:
    '''
    one row per border and MTU; JAO's mirror row (TO-FROM) is dropped.
    zones come from biddingZoneFrom/To, the name gets an MTU and mRID suffix in spanning-backup MTUs
    '''
    rows = [row for row in _system_rows(rows, 'Border_CNEC_') if row['biddingZoneFrom'] < row['biddingZoneTo']]
    if not rows:
        return []
    resolution = _resolution({_parse_utc(row['dateTimeUtc']) for row in rows})
    return [
        FbBorderFlow(
            zone=key,
            timestamp=_parse_utc(row['dateTimeUtc']),
            resolution=resolution,
            border=f"{row['biddingZoneFrom']}-{row['biddingZoneTo']}",
            bidding_zone_from=row['biddingZoneFrom'],
            bidding_zone_to=row['biddingZoneTo'],
            cnec_name=row['cnecName'],
            min_flow=row.get('minFlow'),
            max_flow=row.get('maxFlow'),
            flow_fb=row.get('flowFb'),
            last_modified_on=_parse_utc(row.get('lastModifiedOn')),
        )
        for row in rows
    ]


def parse_fb_monitoring(rows: list[dict], key: str) -> list[FbBorderFlow | FbNetPosition]:
    '''one hour of system rows into both tables: border rows to FbBorderFlow, net positions to FbNetPosition'''
    return [*parse_fb_border_flows(rows, key), *parse_fb_net_positions(rows, key)]


def parse_fb_net_positions(rows: list[dict], key: str) -> list[FbNetPosition]:
    rows = _system_rows(rows, 'NetPosition_')
    if not rows:
        return []
    resolution = _resolution({_parse_utc(row['dateTimeUtc']) for row in rows})
    return [
        FbNetPosition(
            zone=key,
            timestamp=_parse_utc(row['dateTimeUtc']),
            resolution=resolution,
            bidding_zone=row['biddingZoneFrom'],
            cnec_name=row['cnecName'],
            min_net_position=row.get('minFlow'),
            max_net_position=row.get('maxFlow'),
            net_position=row.get('flowFb'),
            last_modified_on=_parse_utc(row.get('lastModifiedOn')),
        )
        for row in rows
    ]

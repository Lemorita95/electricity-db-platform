from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class FbNetPosition(SQLModel, table=True):
    '''
    From JAO's Nordic publication tool / Shadow Price & Flow_FB, the system-generated NetPosition rows.
    One row per bidding zone per MTU: the 12 Nordic zones and the HVDC virtual hubs (SE4_SP, NO2_NK, ...).
    min_net_position / max_net_position: as on JAO's Max and Min Net Pos page.
    net_position: the net position after market coupling (JAO's flowFb), MW, positive is export from that zone.
    For a hub, positive means power flowing from the link into its real zone, so NO2_SK = -1688 means
    NO2 exports 1688 MW over Skagerrak (JAO handbook v1.6, p. 17).
    zone is always 'NORDIC' so the generic range sync works; cnec_name is in the key to keep
    both copies in spanning-backup MTUs.
    '''
    __tablename__ = "fb_net_position"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))  # dateTimeUtc, MTU start
    resolution: str

    bidding_zone: str  # biddingZoneFrom
    cnec_name: str  # cnecName, NetPosition_BZ

    min_net_position: Optional[float] = None  # minFlow, MW
    max_net_position: Optional[float] = None  # maxFlow, MW
    net_position: Optional[float] = None  # flowFb, MW

    last_modified_on: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))  # lastModifiedOn
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', 'bidding_zone', 'cnec_name', name='uq_fb_net_position_key'),
    )

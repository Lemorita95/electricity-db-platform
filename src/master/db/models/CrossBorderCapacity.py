from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class CrossBorderCapacity(SQLModel, table=True):
    '''
    From API's Transmission / 11.3 Cross-Border Capacity for DC Links
    In relation to direct current links, TSOs shall provide updated information on any restrictions placed on the use of available cross-border capacity including through the application of ramping restrictions or intraday transfer limits not later than one hour after the information is known to the ENTSO for Electricity.
    An intraday transfer limit means an intraday capacity limit value taking into account the technical capacity of the interconnector and the security constraints of the grid.
    Information to publish:
    1) Ramping restrictions: It should be treated as a report (figures valid for several months)
    2) intraday transfer limits: for the next day, intraday transfer limits (MW) for each border between bidding zones and per direction, (per market time unit)
    '''
    __tablename__ = "cross_border_capacity"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    flow_destination: str
    flow_origin: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    quantity: float
    unit: str

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_cross_border_capacity_zone_timestamp'),
    )
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class ZonePhysicalFlow(SQLModel, table=True):
    '''
    From API's Transmission / 12.1.G Physical Flows.
    Physical flows between bidding zones per market time unit as closely as possible to real time and at the latest H+1 after the end of the application period.
    Physical flow is defined as the measured power between neighbouring bidding zones.
    For DC links, the values refer to the sending end, unless specified otherwise in the explanatory text accompanying the data publication (some TSOs publish mid-point values). The flow at the receiving end will be lower, and the difference is equal to the transmission loss. See also chapter 3.5 Transmission infrastructure.
    For AC links, losses are deemed as not significant.
    '''
    __tablename__ = "zone_physical_flows"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    flow_destination: str # The domain where energy is going associated with a TimeSeries
    flow_origin: str # The domain where energy is coming from associated with a TimeSeries
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    quantity: float
    unit: str

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_zone_physical_flows_zone_timestamp'),
    )
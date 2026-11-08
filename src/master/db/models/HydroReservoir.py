from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class HydroReservoir(SQLModel, table=True):
    '''
    From API's Generation / 16.1.D Aggregated Filling Rate of Water Reservoirs and Hydro Storage Plants.
    Weekly (P7D): timestamp is the start of the week at midnight market time, quantity is the stored energy in MWh.
    '''
    __tablename__ = "hydro_reservoir"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    quantity: float
    unit: str

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_hydro_reservoir_zone_timestamp'),
    )

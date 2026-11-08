from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Generation(SQLModel, table=True):
    '''
    From API's Generation / 16.1.B&C Actual Generation per Production Type.
    psr_type is the production type (B01 biomass … B20 other, B25 energy storage).
    direction is 'consumption' for the series ENTSO-E reports as load of a production type
    (B10 pumped storage pumping, B25 storage charging), 'generation' otherwise.
    '''
    __tablename__ = "generation"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    psr_type: str
    direction: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    quantity: float
    unit: str

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'psr_type', 'direction', 'timestamp', name='uq_generation_zone_psr_type_direction_timestamp'),
    )

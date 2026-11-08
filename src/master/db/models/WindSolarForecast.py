from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class WindSolarForecast(SQLModel, table=True):
    '''
    From API's Generation / 14.1.D Day-ahead Generation Forecasts for Wind and Solar.
    psr_type: B16 solar, B18 wind offshore, B19 wind onshore.
    '''
    __tablename__ = "wind_solar_forecast"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    psr_type: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    quantity: float
    unit: str

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'psr_type', 'timestamp', name='uq_wind_solar_forecast_zone_psr_type_timestamp'),
    )

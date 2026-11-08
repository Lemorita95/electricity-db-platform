from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class LoadForecast(SQLModel, table=True):
    '''
    From API's Load / 6.1.B Day-ahead Total Load Forecast
    '''
    __tablename__ = "load_forecast"

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
        UniqueConstraint('zone', 'timestamp', name='uq_load_forecast_zone_timestamp'),
    )

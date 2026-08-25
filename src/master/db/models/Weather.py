from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Weather(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    fdir: Optional[float] = None
    ssrd: Optional[float] = None
    temperature_2m: Optional[float] = None
    wind_u_10m: Optional[float] = None
    wind_v_10m: Optional[float] = None

 
    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_weather_zone_timestamp'),
    )

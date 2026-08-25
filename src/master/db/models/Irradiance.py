from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Irradiance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    sis: Optional[float] = None   # Surface Incoming Shortwave — W/m²
    sid: Optional[float] = None   # Surface Incoming Direct — W/m²
    unit: str
 
    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_irradiance_zone_timestamp'),
    )



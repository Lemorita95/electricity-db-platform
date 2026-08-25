from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Demand(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    quantity: float
    unit: str

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_demand_zone_timestamp'),
    )

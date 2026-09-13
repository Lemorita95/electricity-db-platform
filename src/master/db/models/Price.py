from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Price(SQLModel, table=True):
    '''
    From API's Load / 12.1.D Energy Prices
    '''
    __tablename__ = "price"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    resolution: str
    price: float
    currency: str

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', name='uq_price_zone_timestamp'),
    )

from datetime import date, datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Date, TIMESTAMP, UniqueConstraint

# this is needed just to satisfy the code editor as in the class its a common string
if TYPE_CHECKING:
    from master.db.models import GeneratingUnit


class ProductionResource(SQLModel, table=True):
    '''
    From API's Master Data / Production and Generation Units
    '''
    __tablename__ = "production_resource"
 
    id: Optional[int] = Field(default=None, primary_key=True)
 
    resource_mrid: str = Field(index=True) # TimeSeries / registeredResource.mRID
    resource_name: str # TimeSeries / registeredResource.name
    location_name: Optional[str] = None # TimeSeries / registeredResource.location.name
    zone: str = Field(index=True) # TimeSeries / biddingZone_Domain.mRID
 
    control_area_mrid: Optional[str] = None # TimeSeries / ControlArea_Domain / mRID
    provider_mrid: Optional[str] = None # TimeSeries / Provider_MarketParticipant / mRID
    business_type: str # TimeSeries / businessType
    psr_type: str # TimeSeries / MktPSRType / psrType
 
    high_voltage_limit_kv: Optional[float] = None # TimeSeries / MktPSRType / production_PowerSystemResources.highVoltageLimit
    nominal_p_mw: Optional[float] = None # TimeSeries / MktPSRType / nominalIP_PowerSystemResources.nominalP
 
    implementation_date: date = Field(sa_column=Column(Date, nullable=False)) # TimeSeries / implementation_DateAndOrTime.date
    source_ts_mrid: str # TimeSeries / mRID
 
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
 
    units: List["GeneratingUnit"] = Relationship(back_populates="resource")
 
    __table_args__ = (
        UniqueConstraint('resource_mrid', 'implementation_date', name='uq_resource_mrid_impl_date'),
    )
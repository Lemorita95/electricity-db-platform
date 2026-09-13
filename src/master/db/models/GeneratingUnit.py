from datetime import date, datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Date, TIMESTAMP, UniqueConstraint

# this is needed just to satisfy the code editor as in the class its a common string
if TYPE_CHECKING:
    from master.db.models import ProductionResource

class GeneratingUnit(SQLModel, table=True):
    '''
    From API's Master Data / Production and Generation Units
    '''
    __tablename__ = "generating_unit"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    resource_id: int = Field(foreign_key="production_resource.id", index=True)
 
    unit_mrid: str = Field(index=True) # TimeSeries / MktPSRType / GeneratingUnit_PowerSystemResources / mRID
    name: str # TimeSeries / MktPSRType / GeneratingUnit_PowerSystemResources / name
    nominal_p_mw: float # TimeSeries / MktPSRType / GeneratingUnit_PowerSystemResources / nominalP
    psr_type: str # TimeSeries / MktPSRType / GeneratingUnit_PowerSystemResources / generatingUnit_PSRType.psrType
    location_name: Optional[str] = None # TimeSeries / MktPSRType / GeneratingUnit_PowerSystemResources / generatingUnit_Location.name
 
    implementation_date: date = Field(sa_column=Column(Date, nullable=False)) # TimeSeries / implementation_DateAndOrTime.date
 
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
 
    resource: "ProductionResource" = Relationship(back_populates="units")
 
    __table_args__ = (
        UniqueConstraint('unit_mrid', 'implementation_date', name='uq_unit_mrid_impl_date'),
    )
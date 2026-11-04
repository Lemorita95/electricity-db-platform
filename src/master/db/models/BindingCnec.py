from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP

# this is needed just to satisfy the code editor as in the class its a common string
if TYPE_CHECKING:
    from master.db.models import CnecPtdf


class BindingCnec(SQLModel, table=True):
    '''
    From JAO's Nordic publication tool / Shadow Price & Flow_FB, binding CNECs only.
    CNEC (Critical Network Element & Contingency): a grid element monitored under an outage scenario;
    it is binding when its margin (ram) is used up, and its shadow price (EUR/MW) is then > 0.
    zone is always 'NORDIC' so the generic range sync works; cnec_name is in the key to keep
    both copies of a CNEC in spanning-backup MTUs.
    a slot with no binding CNEC looks like a gap to the range sync and is requested again on each sync.
    '''
    __tablename__ = "binding_cnec"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))  # dateTimeUtc, MTU start
    resolution: str

    mr_id: str  # mrId
    cnec_name: str  # cnecName
    cnec_type: Optional[str] = None  # cnecType: BRANCH, ALLOCATION_CONSTRAINT
    tso: Optional[str] = None
    bidding_zone_from: Optional[str] = None  # biddingZoneFrom
    bidding_zone_to: Optional[str] = None  # biddingZoneTo
    cne_name: Optional[str] = None  # cneName, the grid element
    cont_name: Optional[str] = None  # contName, the contingency

    ram: Optional[float] = None  # remaining available margin, MW
    fmax: Optional[float] = None  # highest permissible flow, MW
    fref: Optional[float] = None  # flow at the base case net positions, MW
    flow_fb: Optional[float] = None  # flowFb, flow after market coupling, MW
    shadow_price: float  # shadowPrice, EUR/MW

    last_modified_on: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))  # lastModifiedOn
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    ptdfs: List["CnecPtdf"] = Relationship(back_populates="cnec")

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', 'mr_id', 'cnec_name', name='uq_binding_cnec_key'),
    )

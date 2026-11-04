from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint

# this is needed just to satisfy the code editor as in the class its a common string
if TYPE_CHECKING:
    from master.db.models import BindingCnec


class CnecPtdf(SQLModel, table=True):
    '''
    From JAO's Nordic publication tool / Shadow Price & Flow_FB, the ptdf_<bidding_zone> fields of a binding CNEC.
    PTDF (Power Transfer Distribution Factor): MW change in flow on the CNEC per MW of net export from the zone.
    One row per CNEC and bidding zone, real (SE3) or virtual HVDC hub (SE3_FS), zeros included.
    '''
    __tablename__ = "cnec_ptdf"

    id: Optional[int] = Field(default=None, primary_key=True)
    cnec_id: int = Field(foreign_key="binding_cnec.id", index=True)

    bidding_zone: str  # as in JAO's ptdf_<bidding_zone> field name
    ptdf: Optional[float] = None

    cnec: "BindingCnec" = Relationship(back_populates="ptdfs")

    __table_args__ = (
        UniqueConstraint('cnec_id', 'bidding_zone', name='uq_cnec_ptdf_cnec_zone'),
    )

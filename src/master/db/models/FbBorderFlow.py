from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, Column
from sqlalchemy.dialects.postgresql import TIMESTAMP


class FbBorderFlow(SQLModel, table=True):
    '''
    From JAO's Nordic publication tool / Shadow Price & Flow_FB, the system-generated Border_CNEC rows.
    One row per bidding-zone border per MTU, real (SE3-SE4) or towards an HVDC virtual hub (SE4-SE4_SP);
    JAO publishes both directions as mirrors, only the one with bidding_zone_from < bidding_zone_to is kept.
    min_flow / max_flow: the extremes of the flow on the border within the flow-based domain, each found on its
    own, so two borders at their maximum at once is not guaranteed (JAO handbook v1.6, pp. 8, 13).
    flow_fb: the flow on the border after market coupling.
    These rows never bind (Fmax is a dummy 9999); what limits a border is in binding_cnec.
    zone is always 'NORDIC' so the generic range sync works; cnec_name is in the key to keep
    both copies of a border in spanning-backup MTUs.
    '''
    __tablename__ = "fb_border_flow"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone: str
    timestamp: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))  # dateTimeUtc, MTU start
    resolution: str

    border: str  # 'FROM-TO'
    bidding_zone_from: str  # biddingZoneFrom
    bidding_zone_to: str  # biddingZoneTo
    cnec_name: str  # cnecName, Border_CNEC_FROM-TO

    min_flow: Optional[float] = None  # minFlow, MW
    max_flow: Optional[float] = None  # maxFlow, MW
    flow_fb: Optional[float] = None  # flowFb, MW

    last_modified_on: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))  # lastModifiedOn
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('zone', 'timestamp', 'border', 'cnec_name', name='uq_fb_border_flow_key'),
    )

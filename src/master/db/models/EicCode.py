from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ARRAY, String, TIMESTAMP, UniqueConstraint


class EicCode(SQLModel, table=True):
    '''
    From ENTSO-E's public EIC registry (allocated-eic-codes.xml).
    Flat, not versioned: a full re-fetch always reflects the current registry,
    and upsert_timeseries keeps existing rows fresh (renames, new functions, etc.)
    rather than only ever inserting.
    '''
    __tablename__ = "eic_code"

    id: Optional[int] = Field(default=None, primary_key=True)

    eic_code: str = Field(index=True)  # EICCode_MarketDocument / mRID
    long_name: str  # EICCode_MarketDocument / long_Names.name
    display_name: Optional[str] = None  # display_Names.name
    eic_parent: Optional[str] = None  # eICParent_MarketDocument.mRID
    eic_responsible: Optional[str] = None  # eICResponsible_MarketParticipant.mRID
    functions: List[str] = Field(sa_column=Column(ARRAY(String)))  # Function_Names / name

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint('eic_code', name='uq_eic_code'),
    )

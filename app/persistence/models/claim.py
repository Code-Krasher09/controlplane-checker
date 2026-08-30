"""Claim ORM model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class Claim(Base):
    """Atomic claim extracted from a response."""

    __tablename__ = "claims"
    __table_args__ = (
        Index("idx_claims_response", "response_id"),
    )

    claim_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    response_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="CASCADE"),
        nullable=False,
    )
    claim_index: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    business_impact: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    response: Mapped["Response"] = relationship(
        "Response",
        back_populates="claims",
    )
    nli_results: Mapped[List["NLIResult"]] = relationship(
        "NLIResult",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    claim_evidence_links: Mapped[List["ClaimEvidence"]] = relationship(
        "ClaimEvidence",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    repair_attempts: Mapped[List["RepairAttempt"]] = relationship(
        "RepairAttempt",
        back_populates="failed_claim",
    )

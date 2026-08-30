"""Evidence and ClaimEvidence association ORM models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, UniversalJSONB, utc_now


class Evidence(Base):
    """Retrieved evidence chunk / reference."""

    __tablename__ = "evidence"

    evidence_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_authority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    freshness_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    completeness_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    content_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        UniversalJSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    claim_evidence_links: Mapped[List["ClaimEvidence"]] = relationship(
        "ClaimEvidence",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
    nli_results: Mapped[List["NLIResult"]] = relationship(
        "NLIResult",
        back_populates="evidence",
    )


class ClaimEvidence(Base):
    """Many-to-many join association table between Claim and Evidence."""

    __tablename__ = "claim_evidence"

    claim_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("claims.claim_id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("evidence.evidence_id", ondelete="CASCADE"),
        primary_key=True,
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    claim: Mapped["Claim"] = relationship(
        "Claim",
        back_populates="claim_evidence_links",
    )
    evidence: Mapped["Evidence"] = relationship(
        "Evidence",
        back_populates="claim_evidence_links",
    )

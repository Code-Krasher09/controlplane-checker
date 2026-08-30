"""NLIResult ORM model with strict V1.2 check constraints."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class NLIResult(Base):
    """NLI verification and selective adjudication outcome."""

    __tablename__ = "nli_results"
    __table_args__ = (
        Index("idx_nli_claim", "claim_id"),
        Index("idx_nli_verification_status", "verification_status"),
        Index("idx_nli_adjudication_trigger", "adjudication_trigger"),
        CheckConstraint(
            "verification_status IN ('DIRECT_NLI','ADJUDICATED','ADJUDICATION_INCONCLUSIVE')",
            name="chk_nli_verification_status",
        ),
        CheckConstraint(
            "adjudication_trigger IN ('NONE','NLI_LOW_CONFIDENCE','NLI_CLOSE_TOP2','NLI_EVIDENCE_LABEL_CONFLICT','HIGH_SEVERITY_MARGINAL_NLI')",
            name="chk_nli_adjudication_trigger",
        ),
        CheckConstraint(
            "uncertainty_reason IN ('NONE','NLI_LOW_CONFIDENCE','NLI_CLOSE_TOP2','NLI_EVIDENCE_LABEL_CONFLICT','HIGH_SEVERITY_MARGINAL_NLI','JUDGE_LOW_CONFIDENCE','ADJUDICATION_BUDGET_EXHAUSTED')",
            name="chk_nli_uncertainty_reason",
        ),
        CheckConstraint(
            "verification_status <> 'ADJUDICATION_INCONCLUSIVE' OR final_label IS NULL",
            name="chk_nli_inconclusive_requires_null_label",
        ),
        CheckConstraint(
            "verification_status <> 'DIRECT_NLI' OR final_label IS NOT NULL OR uncertainty_reason = 'ADJUDICATION_BUDGET_EXHAUSTED'",
            name="chk_nli_direct_requires_final_label",
        ),
        CheckConstraint(
            "("
            "(adjudication_trigger = 'NONE' AND verification_status = 'DIRECT_NLI' AND uncertainty_reason = 'NONE') OR "
            "(adjudication_trigger <> 'NONE' AND verification_status IN ('ADJUDICATED','ADJUDICATION_INCONCLUSIVE')) OR "
            "(adjudication_trigger <> 'NONE' AND verification_status = 'DIRECT_NLI' AND uncertainty_reason = 'ADJUDICATION_BUDGET_EXHAUSTED')"
            ")",
            name="chk_nli_trigger_status_consistency",
        ),
    )

    nli_result_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    claim_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("claims.claim_id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("evidence.evidence_id", ondelete="SET NULL"),
        nullable=True,
    )
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    entailment_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    contradiction_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    neutral_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    inference_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nli_confidence: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="DIRECT_NLI",
    )
    adjudication_trigger: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        default="NONE",
    )
    uncertainty_reason: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        default="NONE",
    )
    adjudicator_model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    adjudicator_confidence: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    final_label: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    claim: Mapped["Claim"] = relationship(
        "Claim",
        back_populates="nli_results",
    )
    evidence: Mapped[Optional["Evidence"]] = relationship(
        "Evidence",
        back_populates="nli_results",
    )

"""RiskAssessment ORM model."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, UniversalJSONB, utc_now


class RiskAssessment(Base):
    """Pre-Tier-1 risk assessment and routing decision."""

    __tablename__ = "risk_assessments"

    risk_assessment_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    request_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("requests.request_id", ondelete="CASCADE"),
        nullable=False,
    )
    response_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="CASCADE"),
        nullable=False,
    )
    task_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    response_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    evidence_availability_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    sensitivity_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    severity_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    session_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    cost_state_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    final_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[Dict[str, Any]] = mapped_column(
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
    request: Mapped["Request"] = relationship(
        "Request",
        back_populates="risk_assessments",
    )
    response: Mapped["Response"] = relationship(
        "Response",
        back_populates="risk_assessments",
    )

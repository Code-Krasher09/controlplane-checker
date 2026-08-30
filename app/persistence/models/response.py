"""Response ORM model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class Response(Base):
    """AI-generated or repaired response attempt."""

    __tablename__ = "responses"
    __table_args__ = (
        Index("idx_responses_request", "request_id"),
    )

    response_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    request_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("requests.request_id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    generated_by_model: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("ai_models.model_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    request: Mapped["Request"] = relationship(
        "Request",
        back_populates="responses",
    )
    model: Mapped[Optional["AIModel"]] = relationship(
        "AIModel",
        back_populates="responses",
    )
    policy_events: Mapped[List["PolicyEvent"]] = relationship(
        "PolicyEvent",
        back_populates="response",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="response",
        cascade="all, delete-orphan",
    )
    claims: Mapped[List["Claim"]] = relationship(
        "Claim",
        back_populates="response",
        cascade="all, delete-orphan",
    )
    interventions: Mapped[List["Intervention"]] = relationship(
        "Intervention",
        back_populates="response",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="response",
        cascade="all, delete-orphan",
    )

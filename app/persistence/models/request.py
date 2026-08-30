"""Request ORM model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class Request(Base):
    """Intercepted AI request."""

    __tablename__ = "requests"
    __table_args__ = (
        Index("idx_requests_session", "session_id"),
        Index("idx_requests_status", "status"),
    )

    request_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    application_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("applications.application_id"),
        nullable=False,
    )
    model_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("ai_models.model_id"),
        nullable=True,
    )
    policy_version_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("policy_versions.policy_version_id"),
        nullable=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="REALTIME")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PROCESSING")
    preflight_action: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    preflight_model_budget: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    preflight_output_token_budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application",
        back_populates="requests",
    )
    model: Mapped[Optional["AIModel"]] = relationship(
        "AIModel",
        back_populates="requests",
    )
    policy_version: Mapped[Optional["PolicyVersion"]] = relationship(
        "PolicyVersion",
        back_populates="requests",
    )
    responses: Mapped[List["Response"]] = relationship(
        "Response",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    interventions: Mapped[List["Intervention"]] = relationship(
        "Intervention",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    repair_attempts: Mapped[List["RepairAttempt"]] = relationship(
        "RepairAttempt",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="request",
        cascade="all, delete-orphan",
    )

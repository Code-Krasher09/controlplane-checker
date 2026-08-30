"""PolicyConfig and PolicyVersion ORM models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, UniversalJSONB, utc_now


class PolicyConfig(Base):
    """Application-level policy configuration."""

    __tablename__ = "policy_configs"

    policy_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    application_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("applications.application_id", ondelete="CASCADE"),
        nullable=False,
    )
    policy_name: Mapped[str] = mapped_column(String(150), nullable=False)
    risk_appetite: Mapped[str] = mapped_column(String(30), nullable=False)
    require_grounding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    block_on_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    block_on_policy_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_repair_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_request_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    max_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allow_warn_abstain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    action_precedence: Mapped[Any] = mapped_column(
        UniversalJSONB,
        nullable=False,
        default=lambda: ["BLOCK", "ESCALATE", "REPAIR", "WARN", "ALLOW"],
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application",
        back_populates="policies",
    )
    versions: Mapped[List["PolicyVersion"]] = relationship(
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
    )


class PolicyVersion(Base):
    """Immutable versioned policy snapshot."""

    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version_number", name="uq_policy_version"),
    )

    policy_version_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    policy_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("policy_configs.policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    geography: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thresholds: Mapped[Dict[str, Any]] = mapped_column(
        UniversalJSONB,
        nullable=False,
        default=dict,
    )
    action_rules: Mapped[Dict[str, Any]] = mapped_column(
        UniversalJSONB,
        nullable=False,
        default=dict,
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    policy: Mapped["PolicyConfig"] = relationship(
        "PolicyConfig",
        back_populates="versions",
    )
    requests: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="policy_version",
    )
    interventions: Mapped[List["Intervention"]] = relationship(
        "Intervention",
        back_populates="policy_version",
    )

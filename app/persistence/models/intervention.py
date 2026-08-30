"""Intervention ORM model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class Intervention(Base):
    """Intervention decision triggered by Action Engine."""

    __tablename__ = "interventions"
    __table_args__ = (
        Index("idx_interventions_request", "request_id"),
    )

    intervention_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    request_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("requests.request_id", ondelete="CASCADE"),
        nullable=False,
    )
    response_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    trigger_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("policy_versions.policy_version_id"),
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
        back_populates="interventions",
    )
    response: Mapped[Optional["Response"]] = relationship(
        "Response",
        back_populates="interventions",
    )
    policy_version: Mapped[Optional["PolicyVersion"]] = relationship(
        "PolicyVersion",
        back_populates="interventions",
    )

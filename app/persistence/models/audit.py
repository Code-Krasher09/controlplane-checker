"""AuditEvent ORM model."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, UniversalJSONB, utc_now


class AuditEvent(Base):
    """Immutable audit trail event."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_request", "request_id"),
    )

    event_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    request_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("requests.request_id", ondelete="CASCADE"),
        nullable=True,
    )
    response_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="CASCADE"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    component: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_data: Mapped[Dict[str, Any]] = mapped_column(
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
    request: Mapped[Optional["Request"]] = relationship(
        "Request",
        back_populates="audit_events",
    )
    response: Mapped[Optional["Response"]] = relationship(
        "Response",
        back_populates="audit_events",
    )

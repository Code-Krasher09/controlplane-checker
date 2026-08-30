"""PolicyEvent ORM model for Tier 0 and safety events."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, UniversalJSONB, utc_now


class PolicyEvent(Base):
    """Tier 0 detector or policy compliance event."""

    __tablename__ = "policy_events"

    policy_event_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    response_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    detector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(6, 5), nullable=True)
    matched_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        UniversalJSONB,
        nullable=False,
        default=dict,
    )
    action_taken: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    response: Mapped["Response"] = relationship(
        "Response",
        back_populates="policy_events",
    )

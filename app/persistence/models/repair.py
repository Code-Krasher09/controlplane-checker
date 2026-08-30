"""RepairAttempt ORM model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class RepairAttempt(Base):
    """Repair loop regeneration attempt."""

    __tablename__ = "repair_attempts"

    repair_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    request_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("requests.request_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_response_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="SET NULL"),
        nullable=True,
    )
    repaired_response_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("responses.response_id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_claim_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("claims.claim_id", ondelete="SET NULL"),
        nullable=True,
    )
    repair_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    request: Mapped["Request"] = relationship(
        "Request",
        back_populates="repair_attempts",
    )
    failed_claim: Mapped[Optional["Claim"]] = relationship(
        "Claim",
        back_populates="repair_attempts",
    )

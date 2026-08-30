"""Application ORM model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class Application(Base):
    """Registered enterprise application profile."""

    __tablename__ = "applications"

    application_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application_type: Mapped[str] = mapped_column(String(60), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="REALTIME")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    policies: Mapped[List["PolicyConfig"]] = relationship(
        "PolicyConfig",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    requests: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="application",
    )

"""AI Model metadata ORM model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GUID, utc_now


class AIModel(Base):
    """Registered AI Model provider metadata."""

    __tablename__ = "ai_models"

    model_id: Mapped[UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    deployment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    requests: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="model",
    )
    responses: Mapped[List["Response"]] = relationship(
        "Response",
        back_populates="model",
    )

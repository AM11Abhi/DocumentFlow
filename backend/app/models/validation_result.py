import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, Any
from sqlalchemy import String, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class ValidationStatus(str, PyEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    processing_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_results.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    overall_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status_enum", native_enum=True),
        nullable=False,
    )
    checks: Mapped[Any] = mapped_column(JSONB, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship back to ProcessingResult
    processing_result: Mapped["ProcessingResult"] = relationship(
        "ProcessingResult",
        back_populates="validation_result"
    )

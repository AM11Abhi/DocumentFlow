import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ProcessingResult(Base):
    __tablename__ = "processing_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detection_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    matched_signals: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    
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

    # Relationship back to Document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="processing_result"
    )

    # Relationship to ValidationResult
    validation_result: Mapped[Optional["ValidationResult"]] = relationship(
        "ValidationResult",
        back_populates="processing_result",
        uselist=False,
        cascade="all, delete-orphan",
    )

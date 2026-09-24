"""Classification model for comment toxicity analysis."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Float, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .comment import Comment


class ClassificationBackend(str, Enum):
    """Classification backend services."""
    TYPESAFE = "typesafe"
    MISTRAL = "mistral"
    COMBINED = "combined"


class ClassificationCategory(str, Enum):
    """Classification categories."""
    HATE = "hate"
    HARASSMENT = "harassment"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    SEXUAL = "sexual"
    SPAM = "spam"
    ILLEGAL = "illegal"
    SAFE = "safe"


class ClassificationSeverity(str, Enum):
    """Severity levels for classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Classification(Base):
    """
    Represents a toxicity classification for a comment.
    
    Each comment can have multiple classifications from different backends.
    Classifications include category, severity, confidence, and harmfulness scores.
    """
    
    __tablename__ = "classifications"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Comment being classified
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Classification results
    backend: Mapped[ClassificationBackend] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    category: Mapped[ClassificationCategory] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    severity: Mapped[ClassificationSeverity] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    harmful_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Additional details from the backend
    details: Mapped[dict] = mapped_column(JSON, default={})
    
    # Relationships
    comment: Mapped["Comment"] = relationship(
        "Comment",
        back_populates="classifications"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return (
            f"<Classification(id={self.id}, comment_id={self.comment_id}, "
            f"backend={self.backend}, category={self.category}, "
            f"severity={self.severity})>"
        )
    
    @property
    def is_toxic(self) -> bool:
        """Check if this classification indicates toxicity."""
        return self.category != ClassificationCategory.SAFE
    
    @property
    def risk_level(self) -> str:
        """Get a human-readable risk level."""
        if self.severity == ClassificationSeverity.CRITICAL:
            return "Critical"
        if self.severity == ClassificationSeverity.HIGH:
            return "High"
        if self.severity == ClassificationSeverity.MEDIUM:
            return "Medium"
        return "Low"

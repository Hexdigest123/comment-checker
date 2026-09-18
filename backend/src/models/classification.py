"""
Classification model and result types
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .comment import Comment


class BackendType(str, Enum):
    """Classification backend types."""
    TYPESAFE = "typesafe"
    MISTRAL = "mistral"
    COMBINED = "combined"


class CategoryType(str, Enum):
    """Hate speech categories from TypeSafe Jev."""
    NONE = "none"
    INCITEMENT_TO_CRIME = "incitement_to_crime"
    APPROVAL_OF_ARBITRARY_ACTION = "approval_of_arbitrary_action"
    INCITEMENT_TO_HATRED = "incitement_to_hatred"
    INSULT = "insult"
    THREAT = "threat"
    GLORIFICATION_OF_NAZISM = "glorification_of_nazism"
    RELIGIOUS_DEFAMATION = "religious_defamation"
    OTHER = "other"


class SeverityLevel(str, Enum):
    """Severity levels for classification."""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class Classification(Base):
    """
    Classification result for a comment.
    
    Stores the result of classifying a comment using TypeSafe, Mistral, or combined.
    """

    __tablename__ = "classifications"

    # Comment relation
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    comment: Mapped["Comment"] = relationship("Comment", back_populates="classifications")
    
    # Classification backend
    backend: Mapped[BackendType] = mapped_column(
        SQLEnum(BackendType),
        nullable=False,
        index=True,
    )
    
    # Results
    flagged: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    flagged_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Category
    category: Mapped[Optional[CategoryType]] = mapped_column(
        SQLEnum(CategoryType),
        nullable=True,
    )
    
    # Scores (stored as JSON for flexibility)
    scores: Mapped[Dict[str, float]] = mapped_column(JSON, default={}, nullable=False)
    
    # Confidence and severity
    confidence: Mapped[Optional[float]] = mapped_column(default=None)
    severity: Mapped[Optional[SeverityLevel]] = mapped_column(
        SQLEnum(SeverityLevel),
        default=None,
        nullable=True,
    )
    
    # Harmful probability
    harmful: Mapped[float] = mapped_column(default=0.0, nullable=False)
    
    # Threshold used for this classification
    threshold: Mapped[float] = mapped_column(default=0.3, nullable=False)
    
    # Processing metadata
    processing_time_ms: Mapped[Optional[float]] = mapped_column(default=None)
    
    def __repr__(self) -> str:
        return f"<Classification(id={self.id}, backend={self.backend}, flagged={self.flagged})>"
    
    @property
    def category_label(self) -> str:
        """Get human-readable category label."""
        category_labels = {
            CategoryType.NONE: "No harmful content",
            CategoryType.INCITEMENT_TO_CRIME: "Incitement to crime",
            CategoryType.APPROVAL_OF_ARBITRARY_ACTION: "Approval of arbitrary action",
            CategoryType.INCITEMENT_TO_HATRED: "Incitement to hatred",
            CategoryType.INSULT: "Insult",
            CategoryType.THREAT: "Threat",
            CategoryType.GLORIFICATION_OF_NAZISM: "Glorification of Nazism",
            CategoryType.RELIGIOUS_DEFAMATION: "Religious defamation",
            CategoryType.OTHER: "Other",
        }
        return category_labels.get(self.category, "Unknown")
    
    @property
    def severity_label(self) -> str:
        """Get human-readable severity label."""
        severity_labels = {
            SeverityLevel.NONE: "No harm",
            SeverityLevel.MILD: "Mild: borderline or implicit",
            SeverityLevel.MODERATE: "Moderate: clear harmful intent",
            SeverityLevel.SEVERE: "Severe: blatant, dehumanizing or inciting violence",
        }
        return severity_labels.get(self.severity, "Unknown")

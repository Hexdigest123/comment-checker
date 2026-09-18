"""
Comment and classification models
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .classification import Classification


class CommentStatus(str, Enum):
    """Comment processing status."""
    PENDING = "pending"        # Uploaded, not yet processed
    PROCESSING = "processing"    # Currently being classified
    COMPLETED = "completed"    # Classification finished
    FAILED = "failed"          # Classification failed
    WAITING = "waiting"        # Queued for processing


class CommentPriority(str, Enum):
    """Comment priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Comment(Base):
    """
    Comment model representing a comment to be classified.
    
    Contains all metadata from CSV upload including:
    - Comment text
    - Original author (username)
    - Source URL
    - Context information
    """

    __tablename__ = "comments"

    # Comment content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Original author information
    original_author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_author_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_author_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Source information
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Context (for classification)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # User who uploaded/owns this comment
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user: Mapped[Optional["User"]] = relationship("User", back_populates="comments")
    
    # Processing status
    status: Mapped[CommentStatus] = mapped_column(
        SQLEnum(CommentStatus),
        default=CommentStatus.PENDING,
        nullable=False,
        index=True,
    )
    
    # Priority
    priority: Mapped[CommentPriority] = mapped_column(
        SQLEnum(CommentPriority),
        default=CommentPriority.MEDIUM,
        nullable=False,
    )
    
    # Processing metadata
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional metadata from CSV
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    classifications: Mapped[List["Classification"]] = relationship(
        "Classification",
        back_populates="comment",
        cascade="all, delete-orphan",
    )
    
    # Indexes for performance
    __table_args__ = (
        # Index for status-based queries
        # Index for user-based queries
        # Index for date-based queries
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, status={self.status}, text={self.text[:50]}...)>"

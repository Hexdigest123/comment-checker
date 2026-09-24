"""
Comment model for storing user comments and posts.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .user import User
    from .classification import Classification
    from .external_account import ExternalAccount
    from .comment_embedding import CommentEmbedding
    from .comment_mention import CommentMention


class CommentStatus(str, Enum):
    """Status of a comment in the processing pipeline."""
    PENDING = "pending"       # Uploaded, not yet processed
    PROCESSING = "processing"  # Currently being classified
    COMPLETED = "completed"   # Classification finished
    FAILED = "failed"          # Classification failed
    WAITING = "waiting"        # Queued for processing


class CommentPriority(str, Enum):
    """Comment priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Comment(Base):
    """
    Represents a comment or post from a user or external account.

    Comments can come from:
    - CSV uploads (with original author and link)
    - Social media ingestion (tied to an external account)

    Each comment can have:
    - An internal user (who uploaded it)
    - An external account (who authored it)
    - Multiple classifications (from different backends)
    - An embedding (for semantic search)
    """

    __tablename__ = "comments"

    # Content
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Original author information (from CSV upload)
    original_author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_author_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_author_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Source information
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Date the comment was written on the source platform (from the export);
    # distinct from created_at, which is when the record was ingested
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Context (for classification)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Internal user who uploaded this comment
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="comments",
    )

    # External account who authored this comment (if from social media)
    external_account_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("external_accounts.id", ondelete="SET NULL"),
        index=True,
    )
    external_account: Mapped[Optional["ExternalAccount"]] = relationship(
        "ExternalAccount",
        back_populates="comments",
        foreign_keys=[external_account_id],
    )

    # Platform information (if from social media)
    platform: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    platform_comment_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)

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

    # Community verdict: upvotes minus downvotes (0 = neutral, < 0 = false flag)
    vote_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Additional metadata from CSV (attribute renamed: 'metadata' is reserved by SQLAlchemy)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    classifications: Mapped[list["Classification"]] = relationship(
        "Classification",
        back_populates="comment",
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[list["CommentEmbedding"]] = relationship(
        "CommentEmbedding",
        back_populates="comment",
        cascade="all, delete-orphan",
    )
    mentions: Mapped[list["CommentMention"]] = relationship(
        "CommentMention",
        back_populates="comment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        text_preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"<Comment(id={self.id}, text={text_preview}, status={self.status})>"

    @property
    def author_name(self) -> Optional[str]:
        """Get the author's name (external account, original author, or internal user)."""
        if self.external_account:
            return self.external_account.username or self.external_account.display_name
        if self.original_author:
            return self.original_author
        if self.user:
            return self.user.full_name
        return None

    @property
    def author_platform(self) -> Optional[str]:
        """Get the author's platform (if external)."""
        if self.external_account:
            return self.external_account.platform.value
        return None

    @property
    def has_embedding(self) -> bool:
        """Check if this comment has an embedding."""
        return len(self.embeddings) > 0

    @property
    def is_classified(self) -> bool:
        """Check if this comment has been classified."""
        return len(self.classifications) > 0

    @property
    def is_false_flag(self) -> bool:
        """A comment is classified as a false flag when downvotes outnumber upvotes."""
        return self.vote_score < 0

    @property
    def toxicity_score(self) -> float:
        """Get average toxicity score from classifications."""
        if not self.classifications:
            return 0.0
        return sum(c.harmful_score for c in self.classifications) / len(self.classifications)

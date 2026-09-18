"""Comment model for storing user comments and posts."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .user import User
    from .classification import Classification
    from .external_account import ExternalAccount
    from .comment_embedding import CommentEmbedding


class CommentStatus(str, Enum):
    """Status of a comment in the processing pipeline."""
    PENDING = "pending"       # Waiting to be processed
    PROCESSING = "processing"   # Currently being classified
    COMPLETED = "completed"     # Successfully classified
    FAILED = "failed"           # Classification failed
    WAITING = "waiting"         # Waiting for dependencies


class Comment(Base):
    """
    Represents a comment or post from a user or external account.
    
    Comments can come from:
    - CSV uploads (with username and link)
    - Social media API ingestion (future)
    - Manual entry
    
    Each comment can have:
    - An internal user (who uploaded it)
    - An external account (who authored it)
    - Multiple classifications (from different backends)
    - An embedding (for semantic search)
    """
    
    __tablename__ = "comments"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    
    # Internal user who uploaded this comment
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True
    )
    
    # External account who authored this comment (if from social media)
    external_account_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("external_accounts.id", ondelete="SET NULL"),
        index=True
    )
    
    # Platform information (if from social media)
    platform: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    platform_comment_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Processing status
    status: Mapped[CommentStatus] = mapped_column(
        String(20),
        nullable=False,
        default=CommentStatus.PENDING,
        index=True
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="comments"
    )
    external_account: Mapped[Optional["ExternalAccount"]] = relationship(
        "ExternalAccount",
        back_populates="comments",
        foreign_keys=[external_account_id]
    )
    classifications: Mapped[list["Classification"]] = relationship(
        "Classification",
        back_populates="comment",
        cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["CommentEmbedding"]] = relationship(
        "CommentEmbedding",
        back_populates="comment",
        cascade="all, delete-orphan"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        text_preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"<Comment(id={self.id}, text={text_preview}, status={self.status})>"
    
    @property
    def author_name(self) -> Optional[str]:
        """Get the author's name (external account or internal user)."""
        if self.external_account:
            return self.external_account.username or self.external_account.display_name
        if self.user:
            return self.user.name
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
    def toxicity_score(self) -> float:
        """Get average toxicity score from classifications."""
        if not self.classifications:
            return 0.0
        return sum(c.harmful_score for c in self.classifications) / len(self.classifications)

"""User model for internal application users."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .comment import Comment
    from .refresh_token import RefreshToken
    from .invite_token import InviteToken
    from .password_reset_token import PasswordResetToken
    from .account_cluster import AccountCluster
    from .cluster_connection import ClusterConnection
    from .ai_conversation import AIConversation


class User(Base):
    """
    Represents an internal user of the Comment Checker application.
    
    Users can:
    - Upload comments via CSV
    - Manage their own comments
    - Create and manage clusters (admins only)
    - Use the AI assistant
    - Invite new users (admins only)
    """
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Authentication
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Permissions
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="user",
        foreign_keys="Comment.user_id"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    invite_tokens_created: Mapped[list["InviteToken"]] = relationship(
        "InviteToken",
        back_populates="created_by",
        foreign_keys="InviteToken.created_by_id"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    clusters: Mapped[list["AccountCluster"]] = relationship(
        "AccountCluster",
        back_populates="owner",
        foreign_keys="AccountCluster.owner_id"
    )
    cluster_connections: Mapped[list["ClusterConnection"]] = relationship(
        "ClusterConnection",
        back_populates="created_by",
        foreign_keys="ClusterConnection.created_by_id"
    )
    ai_conversations: Mapped[list["AIConversation"]] = relationship(
        "AIConversation",
        back_populates="user",
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
        return f"<User(id={self.id}, email={self.email}, name={self.name}, admin={self.is_admin})>"
    
    @property
    def comment_count(self) -> int:
        """Get total number of comments uploaded by this user."""
        return len(self.comments)
    
    @property
    def cluster_count(self) -> int:
        """Get number of clusters owned by this user."""
        return len(self.clusters)

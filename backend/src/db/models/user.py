"""
User model for internal application users.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .comment import Comment
    from .token import RefreshToken
    from .account_cluster import AccountCluster
    from .cluster_connection import ClusterConnection
    from .ai_conversation import AIConversation


class User(Base):
    """
    User model representing an authenticated user.

    The application has a single user, auto-created on startup from
    FIRST_ADMIN_USERNAME and FIRST_ADMIN_PASSWORD.

    OWASP Compliance:
    - Passwords are hashed with bcrypt (cost factor >= 12)
    - Sensitive data is never stored in plain text
    """

    __tablename__ = "users"

    # User information
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Password hash (never store plain text)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # User profile
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="user",
        foreign_keys="Comment.user_id",
        cascade="all, delete-orphan",
    )
    clusters: Mapped[list["AccountCluster"]] = relationship(
        "AccountCluster",
        back_populates="owner",
        foreign_keys="AccountCluster.owner_id",
    )
    cluster_connections: Mapped[list["ClusterConnection"]] = relationship(
        "ClusterConnection",
        back_populates="created_by",
        foreign_keys="ClusterConnection.created_by_id",
    )
    ai_conversations: Mapped[list["AIConversation"]] = relationship(
        "AIConversation",
        back_populates="user",
        foreign_keys="AIConversation.user_id",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, is_admin={self.is_admin})>"

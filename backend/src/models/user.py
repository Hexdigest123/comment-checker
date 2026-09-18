"""
User model and schemas
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .token import RefreshToken, InviteToken, PasswordResetToken
    from .comment import Comment


class User(Base):
    """
    User model representing an authenticated user.
    
    OWASP Compliance:
    - Passwords are hashed with bcrypt (cost factor >= 12)
    - Email validation is performed
    - Sensitive data is never stored in plain text
    """

    __tablename__ = "users"

    # User information
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
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
    invite_tokens: Mapped[list["InviteToken"]] = relationship(
        "InviteToken",
        back_populates="created_by",
        foreign_keys="InviteToken.created_by_id",
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, is_admin={self.is_admin})>"

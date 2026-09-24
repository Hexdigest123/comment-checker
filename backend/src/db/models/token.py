"""
Token models for authentication.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .user import User


class TokenStatus(str, Enum):
    """Token status enumeration."""
    ACTIVE = "active"
    USED = "used"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RefreshToken(Base):
    """
    Refresh token model for JWT authentication.

    OWASP Compliance:
    - Tokens are stored in database for revocation
    - Short-lived access tokens, longer-lived refresh tokens
    - Refresh tokens are rotated on use
    - HTTP-only cookies prevent XSS attacks
    """

    __tablename__ = "refresh_tokens"

    # Token data
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # User relation
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    # Token metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[TokenStatus] = mapped_column(
        SQLEnum(TokenStatus),
        default=TokenStatus.ACTIVE,
        nullable=False,
    )

    # Expiry
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Rotation tracking
    is_rotated: Mapped[bool] = mapped_column(Boolean, default=False)
    replaced_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("refresh_tokens.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, status={self.status})>"

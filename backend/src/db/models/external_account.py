"""External social media account model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .comment import Comment
    from .account_cluster import AccountCluster


class PlatformEnum(str, Enum):
    """Supported social media platforms."""
    TWITTER = "twitter"
    X = "x"  # Twitter rebrand
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    REDDIT = "reddit"
    LINKEDIN = "linkedin"
    TWITCH = "twitch"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    OTHER = "other"


class ExternalAccount(Base):
    """
    Represents an external social media account that authored comments.
    
    These accounts are automatically created when ingesting comments from
    social media platforms or CSV files containing username and link info.
    """
    
    __tablename__ = "external_accounts"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Platform information
    platform: Mapped[PlatformEnum] = mapped_column(
        String(20), 
        nullable=False, 
        default=PlatformEnum.OTHER,
        index=True
    )
    platform_user_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Profile information
    username: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    profile_url: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    bio: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metrics
    follower_count: Mapped[Optional[int]] = mapped_column(Integer)
    following_count: Mapped[Optional[int]] = mapped_column(Integer)
    post_count: Mapped[Optional[int]] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Cluster assignment (can be null for unclustered accounts)
    cluster_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("account_clusters.id", ondelete="SET NULL"),
        index=True
    )
    
    # Relationships
    cluster: Mapped[Optional["AccountCluster"]] = relationship(
        "AccountCluster", 
        back_populates="accounts"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", 
        back_populates="external_account",
        foreign_keys="Comment.external_account_id"
    )
    
    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
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
        return f"<ExternalAccount(id={self.id}, platform={self.platform}, username={self.username})>"

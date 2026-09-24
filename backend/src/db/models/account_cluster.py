"""Account cluster model for grouping related social media accounts."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .external_account import ExternalAccount
    from .user import User
    from .cluster_connection import ClusterConnection


class ClusterTypeEnum(str, Enum):
    """Types of account clusters."""
    PERSON = "person"           # Single individual
    ORGANIZATION = "organization"  # Company, org, etc.
    BOT_NETWORK = "bot_network"    # Coordinated bot accounts
    TROLL_FARM = "troll_farm"      # Organized trolling operation
    FAN_CLUB = "fan_club"        # Fan accounts
    SPAM_RING = "spam_ring"        # Spam/phishing network
    UNKNOWN = "unknown"           # Not yet categorized


class DiscoveryMethodEnum(str, Enum):
    """How the cluster was discovered."""
    MANUAL = "manual"             # Created by admin
    AUTO_USERNAME = "auto_username"  # Same username on same platform
    AUTO_PROFILE = "auto_profile"    # Similar profile info
    AUTO_BEHAVIOR = "auto_behavior"  # Similar posting patterns
    AUTO_LINKS = "auto_links"       # Cross-platform links in bios


class AccountCluster(Base):
    """
    Represents a group of social media accounts that belong to the same entity.
    
    Accounts can be automatically grouped by:
    - Same username on the same platform (admin manual linkage)
    - Manual linkage by admins
    
    Auto-clustering rules:
    - Comments on the same platform with the same username are automatically grouped
    - Manual connections by admins can link clusters together
    """
    
    __tablename__ = "account_clusters"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Cluster information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    cluster_type: Mapped[ClusterTypeEnum] = mapped_column(
        String(20),
        nullable=False,
        default=ClusterTypeEnum.UNKNOWN
    )
    
    # Visualization
    color: Mapped[Optional[str]] = mapped_column(String(7), default="#666666")
    icon: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Ownership (which internal user owns/manages this cluster)
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True
    )
    
    # Discovery
    discovery_method: Mapped[DiscoveryMethodEnum] = mapped_column(
        String(20),
        nullable=False,
        default=DiscoveryMethodEnum.MANUAL
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    owner: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="clusters"
    )
    accounts: Mapped[list["ExternalAccount"]] = relationship(
        "ExternalAccount",
        back_populates="cluster",
        foreign_keys="ExternalAccount.cluster_id"
    )
    
    # Connections to other clusters
    connections_out: Mapped[list["ClusterConnection"]] = relationship(
        "ClusterConnection",
        back_populates="cluster_a",
        foreign_keys="ClusterConnection.cluster_a_id"
    )
    connections_in: Mapped[list["ClusterConnection"]] = relationship(
        "ClusterConnection",
        back_populates="cluster_b",
        foreign_keys="ClusterConnection.cluster_b_id"
    )
    
    # Metadata
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    toxicity_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
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
        return f"<AccountCluster(id={self.id}, name={self.name}, type={self.cluster_type})>"
    
    @property
    def platform_distribution(self) -> dict[str, int]:
        """Get distribution of platforms in this cluster."""
        from collections import Counter
        if not self.accounts:
            return {}
        return dict(Counter(account.platform.value for account in self.accounts))
    
    @property
    def total_followers(self) -> int:
        """Get total followers across all accounts."""
        return sum(
            (account.follower_count or 0) 
            for account in self.accounts
        )

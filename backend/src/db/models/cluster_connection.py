"""Cluster connection model for manual linkages between clusters."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .account_cluster import AccountCluster
    from .user import User


class ConnectionTypeEnum(str, Enum):
    """Types of connections between clusters."""
    SAME_PERSON = "same_person"         # Same individual
    RELATED = "related"                 # Related individuals
    AFFILIATED = "affiliated"           # Affiliated organizations
    COORDINATED = "coordinated"         # Coordinated activity
    SHARED_INFRASTRUCTURE = "shared_infrastructure"  # Same VPN, server, etc.
    FINANCIAL = "financial"             # Financial connections
    FAMILY = "family"                   # Family members
    EMPLOYMENT = "employment"           # Employer-employee
    OTHER = "other"                     # Other connection


class ConnectionStatusEnum(str, Enum):
    """Status of a connection."""
    PROPOSED = "proposed"               # Suggested, not yet confirmed
    CONFIRMED = "confirmed"             # Verified by admin
    REJECTED = "rejected"               # Determined to be incorrect
    DISPUTED = "disputed"               # Under review


class ClusterConnection(Base):
    """
    Represents a manual connection between two account clusters.
    
    These connections are created by admins to indicate relationships
    between different clusters that may represent the same entity
    or related entities.
    """
    
    __tablename__ = "cluster_connections"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Connected clusters (bidirectional)
    cluster_a_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("account_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    cluster_b_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("account_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Connection details
    connection_type: Mapped[ConnectionTypeEnum] = mapped_column(
        String(30),
        nullable=False,
        default=ConnectionTypeEnum.SAME_PERSON
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5
    )  # 0-1, where 1 = certain
    
    # Status
    status: Mapped[ConnectionStatusEnum] = mapped_column(
        String(20),
        nullable=False,
        default=ConnectionStatusEnum.PROPOSED
    )
    
    # Evidence and notes
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Who created this connection
    created_by_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True
    )
    
    # Relationships
    cluster_a: Mapped["AccountCluster"] = relationship(
        "AccountCluster",
        back_populates="connections_out",
        foreign_keys=[cluster_a_id]
    )
    cluster_b: Mapped["AccountCluster"] = relationship(
        "AccountCluster",
        back_populates="connections_in",
        foreign_keys=[cluster_b_id]
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="cluster_connections"
    )
    
    # Metadata
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    verified_by_id: Mapped[Optional[str]] = mapped_column(String(36))
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
        return (
            f"<ClusterConnection(id={self.id}, "
            f"a={self.cluster_a_id}, b={self.cluster_b_id}, "
            f"type={self.connection_type})>"
        )
    
    @property
    def is_confirmed(self) -> bool:
        """Check if connection is confirmed."""
        return self.status == ConnectionStatusEnum.CONFIRMED
    
    @property
    def combined_toxicity(self) -> float:
        """Get average toxicity of both clusters."""
        return (self.cluster_a.toxicity_score + self.cluster_b.toxicity_score) / 2

"""
Pydantic schemas for account clusters and connections
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class ClusterBase(BaseModel):
    """Base schema for account clusters."""
    name: str = Field(..., description="Cluster name")
    description: Optional[str] = Field(None, description="Cluster description")
    cluster_type: str = Field(
        default="unknown",
        description="Cluster type: person, organization, bot_network, troll_farm, fan_club, spam_ring, unknown"
    )
    color: Optional[str] = Field(None, description="Color for visualization (hex code)")
    icon: Optional[str] = Field(None, description="Icon identifier")


class ClusterCreate(ClusterBase):
    """Schema for creating a new cluster."""
    discovery_method: Optional[str] = Field(
        default="manual",
        description="Discovery method: manual, auto_username, auto_profile, auto_behavior, auto_links"
    )
    account_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="List of account IDs to add to the cluster"
    )


class ClusterUpdate(BaseModel):
    """Schema for updating a cluster."""
    name: Optional[str] = Field(None, description="Cluster name")
    description: Optional[str] = Field(None, description="Cluster description")
    cluster_type: Optional[str] = Field(None, description="Cluster type")
    color: Optional[str] = Field(None, description="Color for visualization")
    icon: Optional[str] = Field(None, description="Icon identifier")
    is_verified: Optional[bool] = Field(None, description="Whether the cluster is verified")


class ClusterAccountInfo(BaseModel):
    """Account information within a cluster."""
    id: str
    platform: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    follower_count: Optional[int] = None
    verified: bool = False
    comment_count: int = 0


class ClusterConnectionInfo(BaseModel):
    """Connection information for a cluster."""
    id: str
    cluster_a_id: str
    cluster_b_id: str
    cluster_b_name: Optional[str] = None
    connection_type: str
    confidence: float = 0.5
    status: str
    created_at: datetime


class ClusterResponse(ClusterBase):
    """Full schema for cluster response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="Cluster ID")
    name: str
    description: Optional[str] = None
    cluster_type: str
    discovery_method: str
    owner_id: Optional[int] = Field(None, description="ID of the user who owns this cluster")
    owner_name: Optional[str] = Field(None, description="Name of the user who owns this cluster")
    color: Optional[str] = None
    icon: Optional[str] = None
    is_verified: bool = False
    comment_count: int = 0
    toxicity_score: float = 0.0
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    accounts: List[ClusterAccountInfo] = Field(default_factory=list)
    connections_out: List[ClusterConnectionInfo] = Field(default_factory=list)
    connections_in: List[ClusterConnectionInfo] = Field(default_factory=list)
    platform_distribution: Dict[str, int] = Field(default_factory=dict)
    total_followers: int = 0


class ClusterListResponse(BaseModel):
    """Schema for cluster list item."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    description: Optional[str] = None
    cluster_type: str
    discovery_method: str
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_verified: bool = False
    comment_count: int = 0
    toxicity_score: float = 0.0
    last_activity_at: Optional[datetime] = None
    account_count: int = 0
    created_at: datetime
    updated_at: datetime


class ClusterGraphNode(BaseModel):
    """Node in cluster graph."""
    id: str
    name: str
    type: str  # 'platform', 'cluster', 'account' or 'comment'
    cluster_type: Optional[str] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    account_id: Optional[str] = None
    comment_count: int = 0
    toxicity_score: float = 0.0
    color: str
    icon: Optional[str] = None
    index: int


class ClusterGraphLink(BaseModel):
    """Link in cluster graph."""
    source: int
    target: int
    type: str  # 'platform', 'connection', 'belongs_to' or 'comment'
    connection_type: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None


class ClusterGraphResponse(BaseModel):
    """Schema for cluster graph data."""
    nodes: List[ClusterGraphNode] = Field(default_factory=list)
    links: List[ClusterGraphLink] = Field(default_factory=list)


class ConnectionBase(BaseModel):
    """Base schema for cluster connections."""
    cluster_a_id: str = Field(..., description="First cluster ID")
    cluster_b_id: str = Field(..., description="Second cluster ID")
    connection_type: str = Field(
        default="same_person",
        description="Connection type: same_person, same_organization, coordinated, shared_device, other"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence level (0-1)"
    )
    evidence: Optional[str] = Field(None, description="Evidence supporting the connection")
    notes: Optional[str] = Field(None, description="Additional notes")


class ConnectionCreate(ConnectionBase):
    """Schema for creating a new connection."""
    pass


class ConnectionUpdate(BaseModel):
    """Schema for updating a connection."""
    connection_type: Optional[str] = Field(None, description="Connection type")
    confidence: Optional[float] = Field(None, description="Confidence level")
    evidence: Optional[str] = Field(None, description="Evidence")
    notes: Optional[str] = Field(None, description="Notes")


class ConnectionResponse(ConnectionBase):
    """Full schema for connection response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="Connection ID")
    cluster_a_id: str
    cluster_a_name: Optional[str] = None
    cluster_b_id: str
    cluster_b_name: Optional[str] = None
    connection_type: str
    confidence: float
    status: str
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    evidence: Optional[str] = None
    notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    verified_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConnectionListResponse(BaseModel):
    """Schema for connection list item."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    cluster_a_id: str
    cluster_a_name: Optional[str] = None
    cluster_b_id: str
    cluster_b_name: Optional[str] = None
    connection_type: str
    confidence: float
    status: str
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None
    evidence: Optional[str] = None
    notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    verified_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

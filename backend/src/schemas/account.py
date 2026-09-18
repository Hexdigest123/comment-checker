"""
Pydantic schemas for external accounts
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from .pagination import PageParams, PageResponse


class ExternalAccountBase(BaseModel):
    """Base schema for external accounts."""
    platform: str = Field(..., description="Social media platform (twitter, facebook, youtube, etc.)")
    username: Optional[str] = Field(None, description="Username on the platform")
    display_name: Optional[str] = Field(None, description="Display name")
    profile_url: Optional[str] = Field(None, description="URL to the profile")
    avatar_url: Optional[str] = Field(None, description="URL to the avatar image")
    bio: Optional[str] = Field(None, description="User bio/description")
    follower_count: Optional[int] = Field(None, description="Number of followers")
    following_count: Optional[int] = Field(None, description="Number of accounts following")
    post_count: Optional[int] = Field(None, description="Number of posts")
    verified: bool = Field(default=False, description="Whether the account is verified")
    is_active: bool = Field(default=True, description="Whether the account is active")


class ExternalAccountCreate(ExternalAccountBase):
    """Schema for creating a new external account."""
    platform_user_id: Optional[str] = Field(None, description="Platform-specific user ID")


class ExternalAccountUpdate(BaseModel):
    """Schema for updating an external account."""
    platform: Optional[str] = Field(None, description="Social media platform")
    username: Optional[str] = Field(None, description="Username on the platform")
    display_name: Optional[str] = Field(None, description="Display name")
    profile_url: Optional[str] = Field(None, description="URL to the profile")
    avatar_url: Optional[str] = Field(None, description="URL to the avatar image")
    bio: Optional[str] = Field(None, description="User bio/description")
    follower_count: Optional[int] = Field(None, description="Number of followers")
    following_count: Optional[int] = Field(None, description="Number of accounts following")
    post_count: Optional[int] = Field(None, description="Number of posts")
    verified: Optional[bool] = Field(None, description="Whether the account is verified")
    is_active: Optional[bool] = Field(None, description="Whether the account is active")


class ExternalAccountClusterInfo(BaseModel):
    """Cluster information for an external account."""
    id: str
    name: str
    type: str
    toxicity_score: float = 0.0
    comment_count: int = 0


class ExternalAccountCommentInfo(BaseModel):
    """Comment information for an external account."""
    id: str
    text: str
    status: str
    created_at: datetime


class ExternalAccountResponse(ExternalAccountBase):
    """Full schema for external account response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="Account ID")
    platform: str
    platform_user_id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    verified: bool = False
    cluster_id: Optional[str] = Field(None, description="ID of the cluster this account belongs to")
    is_active: bool = True
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    comments: List[ExternalAccountCommentInfo] = Field(default_factory=list)
    cluster: Optional[ExternalAccountClusterInfo] = None


class ExternalAccountListResponse(BaseModel):
    """Schema for external account list item."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    platform: str
    platform_user_id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    verified: bool = False
    cluster_id: Optional[str] = None
    is_active: bool = True
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

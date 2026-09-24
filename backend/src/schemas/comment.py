"""
Comment schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CommentBase(BaseModel):
    """Base comment schema."""
    text: str = Field(..., description="Comment text")


class CommentCreate(CommentBase):
    """Schema for creating a new comment."""
    original_author: Optional[str] = Field(default=None, description="Original author username")
    original_author_id: Optional[str] = Field(default=None, description="Original author ID")
    original_author_url: Optional[str] = Field(default=None, description="Original author profile URL")
    source_url: Optional[str] = Field(default=None, description="Source URL (e.g., social media post URL)")
    source_platform: Optional[str] = Field(default=None, description="Source platform (e.g., instagram, twitter)")
    context: Optional[str] = Field(default=None, description="Context for classification")
    priority: Optional[str] = Field(default="medium", description="Priority level (low, medium, high)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class CommentUpdate(BaseModel):
    """Schema for updating a comment."""
    text: Optional[str] = Field(default=None, description="Updated comment text")
    original_author: Optional[str] = Field(default=None, description="Updated original author")
    source_url: Optional[str] = Field(default=None, description="Updated source URL")
    context: Optional[str] = Field(default=None, description="Updated context")
    priority: Optional[str] = Field(default=None, description="Updated priority")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Updated metadata")


class CommentResponse(BaseModel):
    """Comment response schema."""
    id: int
    text: str
    original_author: Optional[str]
    original_author_id: Optional[str]
    original_author_url: Optional[str]
    source_url: Optional[str]
    source_platform: Optional[str]
    context: Optional[str]
    user_id: Optional[int]
    status: str
    priority: str
    processed_at: Optional[datetime]
    processing_started_at: Optional[datetime]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    # Classification results (if any)
    classifications: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """Comment list item schema."""
    id: int
    text: str
    original_author: Optional[str]
    source_url: Optional[str]
    source_platform: Optional[str]
    status: str
    priority: str
    processed_at: Optional[datetime]
    created_at: datetime
    classifications: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class CommentStatusResponse(BaseModel):
    """Comment status response."""
    id: int
    status: str
    processed_at: Optional[datetime]
    processing_started_at: Optional[datetime]
    error_message: Optional[str]


class CommentSearchResponse(BaseModel):
    """Semantic search result item with similarity score."""
    id: int
    text: str
    original_author: Optional[str] = None
    source_url: Optional[str] = None
    source_platform: Optional[str] = None
    status: str
    similarity: float
    created_at: datetime
    
    class Config:
        from_attributes = True

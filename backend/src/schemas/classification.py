"""
Classification schemas
"""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ClassificationBase(BaseModel):
    """Base classification schema."""
    backend: str = Field(..., description="Classification backend (typesafe, mistral, combined)")
    flagged: bool = Field(..., description="Whether the comment was flagged")


class ClassificationCreate(ClassificationBase):
    """Schema for creating a classification."""
    comment_id: int = Field(..., description="Comment ID to classify")
    flagged_by: Optional[str] = Field(default=None, description="What flagged the comment")
    category: Optional[str] = Field(default=None, description="Category of harmful content")
    scores: Dict[str, float] = Field(default={}, description="Category scores")
    confidence: Optional[float] = Field(default=None, description="Confidence score")
    severity: Optional[str] = Field(default=None, description="Severity level")
    harmful: float = Field(default=0.0, description="Harmful probability")
    threshold: float = Field(default=0.3, description="Threshold used")


class ClassificationResponse(BaseModel):
    """Classification response schema."""
    id: str
    comment_id: int
    backend: str
    flagged: bool
    category: Optional[str]
    severity: Optional[str]
    confidence: Optional[float]
    harmful_score: float
    details: Optional[Dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ClassificationListResponse(BaseModel):
    """Classification list item schema."""
    id: str
    comment_id: int
    backend: str
    flagged: bool
    category: Optional[str]
    severity: Optional[str]
    confidence: Optional[float]
    harmful_score: float
    created_at: datetime

    class Config:
        from_attributes = True


class ClassificationStatsResponse(BaseModel):
    """Classification statistics response."""
    backend: str
    total: int
    flagged: int
    not_flagged: int
    flagged_percentage: float
    average_harmful: float
    average_confidence: Optional[float]
    category_distribution: Dict[str, int]
    severity_distribution: Dict[str, int]
    
    class Config:
        from_attributes = True

"""
User schemas for request/response validation
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(default=None, description="User full name")
    password: str = Field(..., description="User password")


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    full_name: Optional[str] = Field(default=None, description="New full name")
    current_password: Optional[str] = Field(default=None, description="Current password for verification")
    new_password: Optional[str] = Field(default=None, min_length=8, description="New password (min 8 characters)")


class UserResponse(BaseModel):
    """User response schema (without sensitive data)."""
    id: int
    username: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class MeResponse(BaseModel):
    """Current user response schema."""
    id: int
    username: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

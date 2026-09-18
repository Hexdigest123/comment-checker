"""
Token schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    """Token response schema."""
    id: int
    token: str
    status: str
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True


class InviteTokenCreate(BaseModel):
    """Create invite token request schema."""
    email: EmailStr = Field(..., description="Email of the user to invite")


class InviteTokenResponse(BaseModel):
    """Invite token response schema."""
    id: int
    email: EmailStr
    token: str
    status: str
    created_by_id: int
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class InviteTokenListResponse(BaseModel):
    """Invite token list item schema."""
    id: int
    email: EmailStr
    status: str
    created_by_id: int
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: EmailStr = Field(..., description="Email address to reset password for")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class PasswordResetResponse(BaseModel):
    """Password reset response schema."""
    message: str = Field(..., description="Reset message")
    success: bool = Field(..., description="Whether reset was successful")

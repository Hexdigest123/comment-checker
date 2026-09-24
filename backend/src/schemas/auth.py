"""
Authentication schemas
"""

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request schema."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """Login response schema."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    refresh_token: str = Field(..., description="Refresh token")
    refresh_expires_in: int = Field(..., description="Refresh token expiry in seconds")
    user: dict = Field(..., description="User information")


class RefreshRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str = Field(..., description="Refresh token")


class RefreshResponse(BaseModel):
    """Refresh token response schema."""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    refresh_token: Optional[str] = Field(default=None, description="New refresh token (if rotated)")
    refresh_expires_in: Optional[int] = Field(default=None, description="New refresh token expiry in seconds")


class LogoutResponse(BaseModel):
    """Logout response schema."""
    message: str = Field(default="Logged out successfully", description="Logout message")
    revoked: bool = Field(default=True, description="Whether refresh token was revoked")

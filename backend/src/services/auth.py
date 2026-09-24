"""
Authentication service
Provides password hashing, verification, and JWT token utilities
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from ..config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

# Password hashing context - OWASP: Use bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string
        
    OWASP Compliance:
    - Uses bcrypt with automatic cost factor
    - Never stores plain text passwords
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of claims to include in token
        expires_delta: Optional timedelta for expiration (default: settings.access_token_expire_minutes)
        
    Returns:
        Encoded JWT token string
        
    OWASP Compliance:
    - Short-lived tokens (default 15-30 minutes)
    - Signed with secure algorithm (HS256)
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.algorithm,
    )
    
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Dictionary of claims to include in token
        expires_delta: Optional timedelta for expiration (default: settings.refresh_token_expire_days)
        
    Returns:
        Encoded JWT token string
        
    OWASP Compliance:
    - Longer-lived than access tokens but still limited
    - Used to obtain new access tokens
    - Can be revoked
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": secrets.token_urlsafe(16),
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.algorithm,
    )

    return encoded_jwt


def get_token_from_header(authorization: str) -> Optional[str]:
    """
    Extract token from Authorization header.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Token string or None if not found
    """
    if not authorization:
        return None
    
    parts = authorization.split()
    if len(parts) != 2:
        return None
    
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    
    return token


def get_token_from_cookie(request) -> Optional[str]:
    """
    Extract token from request cookies.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Token string or None if not found
        
    OWASP Compliance:
    - HTTP-only cookies prevent XSS attacks
    - Secure flag in production
    """
    token = request.cookies.get(settings.access_token_cookie_name)
    if token:
        return token
    return None

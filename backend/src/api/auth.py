"""
Authentication API router
OWASP-compliant JWT authentication with access and refresh tokens
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import User, RefreshToken, TokenStatus
from ..schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutResponse,
)
from ..services.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
)
from ..services.token import (
    create_refresh_token_db,
    get_refresh_token_by_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from ..services.user import get_user_by_username, get_user_by_id

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])

# Password hashing context - OWASP: Use bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for access token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> User:
    """
    Get current user from JWT access token.
    
    OWASP Compliance:
    - Validates JWT signature
    - Validates token expiry
    - Retrieves user from database
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.algorithm],
        )
        raw_user_id = payload.get("sub")
        if raw_user_id is None:
            raise credentials_exception
        user_id = int(raw_user_id)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise credentials_exception

        return user
    except (JWTError, ValueError, TypeError) as e:
        logger.warning(f"JWT validation error: {e}")
        raise credentials_exception


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current active user.
    
    OWASP Compliance:
    - Checks if user is active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Get current admin user.
    
    OWASP Compliance:
    - Checks if user is admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> LoginResponse:
    """
    Login endpoint - Returns access token and refresh token.
    
    OWASP Compliance:
    - Rate limiting should be applied (configured in main app)
    - Password hashing with bcrypt
    - Secure token generation
    - HTTP-only cookies for refresh tokens
    """
    user = await get_user_by_username(db, login_data.username)

    if user is None or not user.is_active:
        logger.warning(f"Login failed: user not found or inactive - {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password - OWASP: Use constant-time comparison
    if not verify_password(login_data.password, user.password_hash):
        logger.warning(f"Login failed: incorrect password - {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "is_admin": user.is_admin},
        expires_delta=access_token_expires,
    )
    refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=refresh_token_expires,
    )
    
    # Store refresh token in database - OWASP: Store hash only
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "")
    
    await create_refresh_token_db(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    # Set refresh token in HTTP-only cookie - OWASP: Prevent XSS
    refresh_token_expires_seconds = int(refresh_token_expires.total_seconds())
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        max_age=refresh_token_expires_seconds,
        path="/api/v1/auth/refresh",
    )
    
    logger.info(f"User logged in: {user.username}")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        refresh_token=refresh_token,
        refresh_expires_in=refresh_token_expires_seconds,
        user={
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
        },
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_request: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> RefreshResponse:
    """
    Refresh access token using refresh token.
    
    OWASP Compliance:
    - Rotate refresh tokens (issue new refresh token on each use)
    - Validate refresh token from database
    - HTTP-only cookies
    """
    refresh_token = refresh_request.refresh_token
    
    if not refresh_token:
        # Try to get from cookie
        refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db_refresh_token = await get_refresh_token_by_token(db, refresh_token)
    
    if db_refresh_token is None or db_refresh_token.status != TokenStatus.ACTIVE:
        logger.warning(f"Refresh token validation failed: token not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if db_refresh_token.expires_at < datetime.now(timezone.utc):
        # Token expired - revoke it
        await revoke_refresh_token(db, db_refresh_token.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user_by_id(db, db_refresh_token.user_id)
    
    if user is None or not user.is_active:
        await revoke_refresh_token(db, db_refresh_token.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "is_admin": user.is_admin},
        expires_delta=access_token_expires,
    )
    
    # Rotate refresh token - OWASP: Prevent refresh token theft
    new_refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=new_refresh_token_expires,
    )
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "")
    
    await rotate_refresh_token(
        db=db,
        old_token_id=db_refresh_token.id,
        new_token=new_refresh_token,
        expires_at=datetime.now(timezone.utc) + new_refresh_token_expires,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    new_refresh_token_expires_seconds = int(new_refresh_token_expires.total_seconds())
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        max_age=new_refresh_token_expires_seconds,
        path="/api/v1/auth/refresh",
    )
    
    logger.info(f"Token refreshed for user: {user.username}")
    
    return RefreshResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        refresh_token=new_refresh_token,
        refresh_expires_in=new_refresh_token_expires_seconds,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LogoutResponse:
    """
    Logout endpoint - Revokes refresh token.
    
    OWASP Compliance:
    - Revokes refresh token in database
    - Clears HTTP-only cookie
    """
    refresh_token = request.cookies.get("refresh_token")
    
    if refresh_token:
        db_refresh_token = await get_refresh_token_by_token(db, refresh_token)
        if db_refresh_token:
            await revoke_refresh_token(db, db_refresh_token.id)
    
    # Clear refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth/refresh",
        httponly=True,
        secure=settings.production,
        samesite="strict",
    )
    
    logger.info(f"User logged out: {current_user.username}")
    
    return LogoutResponse(
        message="Logged out successfully",
        revoked=refresh_token is not None,
    )


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LogoutResponse:
    """
    Logout from all sessions - Revokes all refresh tokens for user.
    
    OWASP Compliance:
    - Revokes all refresh tokens for the user
    """
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id)
        .values(status=TokenStatus.REVOKED)
    )
    await db.commit()
    
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth/refresh",
        httponly=True,
        secure=settings.production,
        samesite="strict",
    )
    
    logger.info(f"User logged out from all sessions: {current_user.username}")
    
    return LogoutResponse(
        message="Logged out from all sessions",
        revoked=True,
    )

"""
Users API router
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from ..config import get_settings
from ..db.session import get_async_db
from ..models import User, Comment, Classification
from ..schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    MeResponse,
    PageParams,
    PageResponse,
)
from ..services.user import (
    get_user_by_id,
    get_user_by_email,
    create_user,
    update_user,
    delete_user,
    get_users_paginated,
)
from ..api.auth import get_current_user, get_current_active_user, get_current_admin_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=MeResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MeResponse:
    """Get current user profile."""
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id_endpoint(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get user by ID."""
    # Check if current user can access this user
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    user = await get_user_by_id(db, user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Update current user profile."""
    # Verify current password if changing password
    if user_update.new_password and not user_update.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password required when changing password",
        )
    
    if user_update.current_password and user_update.new_password:
        from ..services.auth import verify_password
        if not verify_password(user_update.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
    
    user = await update_user(db, current_user.id, user_update, current_user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.get("/", response_model=PageResponse[UserListResponse])
async def list_users(
    params: PageParams = Depends(),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> PageResponse[UserListResponse]:
    """
    List all users (admin only).
    
    Supports pagination, search, and sorting.
    """
    # Add search filter
    search_filter = None
    if params.search:
        search_pattern = f"%{params.search}%"
        search_filter = or_(
            User.email.ilike(search_pattern),
            User.full_name.ilike(search_pattern),
        )
    
    result = await get_users_paginated(
        db=db,
        page=params.page,
        page_size=params.page_size,
        sort_by=params.sort_by or "created_at",
        sort_order=params.sort_order or "desc",
        filter_condition=search_filter,
    )
    
    return result


@router.post("/", response_model=UserResponse)
async def create_user_endpoint(
    user_create: UserCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    """Create a new user (admin only)."""
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_create.email)
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = await create_user(db, user_create, is_admin=False)
    
    logger.info(f"User created by admin: {user.email}")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: int,
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    """Update user (admin only)."""
    user = await update_user(db, user_id, user_update, current_user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """Delete user (admin only)."""
    # Prevent deleting self
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    
    await delete_user(db, user_id)
    
    logger.info(f"User deleted by admin: {user_id}")

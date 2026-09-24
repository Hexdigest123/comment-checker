"""
Users API router
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_async_db
from ..db.models import User
from ..schemas import (
    UserUpdate,
    UserResponse,
    MeResponse,
)
from ..services.user import update_user
from ..api.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users"])


@router.get("/me", response_model=MeResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MeResponse:
    """Get current user profile."""
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
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
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login=user.last_login,
    )

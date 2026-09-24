"""
User service for user operations.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..schemas import UserCreate, UserUpdate
from .auth import get_password_hash

logger = logging.getLogger(__name__)

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    Get a user by ID.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        User if found, None otherwise
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    Get a user by username.

    Args:
        db: Database session
        username: Username

    Returns:
        User if found, None otherwise
    """
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def create_user(
    db: AsyncSession,
    user_create: UserCreate,
    is_admin: bool = False,
) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        user_create: User creation data
        is_admin: Whether the user should be an admin

    Returns:
        Created user
    """
    user = User(
        username=user_create.username,
        full_name=user_create.full_name,
        password_hash=get_password_hash(user_create.password),
        is_admin=is_admin,
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"User created: {user.username} (id={user.id})")

    return user

async def update_user(
    db: AsyncSession,
    user_id: int,
    user_update: UserUpdate,
    current_user: Optional[User] = None,
) -> Optional[User]:
    """
    Update a user's profile.

    Only updates fields that are provided. Password changes should be
    verified by the caller (the API layer verifies the current password).

    Args:
        db: Database session
        user_id: User ID to update
        user_update: User update data
        current_user: The user performing the update (unused, kept for API compat)

    Returns:
        Updated user if found, None otherwise
    """
    user = await get_user_by_id(db, user_id)

    if user is None:
        return None

    if user_update.full_name is not None:
        user.full_name = user_update.full_name

    if user_update.new_password:
        user.password_hash = get_password_hash(user_update.new_password)
        user.password_changed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    logger.info(f"User updated: {user.username} (id={user.id})")

    return user

"""
First admin service
Auto-creates the single admin user on application startup if no admin exists
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import User
from ..services.auth import get_password_hash
from ..services.user import get_user_by_username, create_user

settings = get_settings()

logger = logging.getLogger(__name__)


async def first_admin_exists(db: AsyncSession) -> bool:
    """
    Check if at least one admin user exists.

    Args:
        db: Database session

    Returns:
        True if admin exists, False otherwise
    """
    result = await db.execute(
        select(User).where(User.is_admin == True).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def create_first_admin_on_startup() -> Optional[User]:
    """
    Create the first admin user on startup if no admin exists.

    Uses FIRST_ADMIN_USERNAME and FIRST_ADMIN_PASSWORD from environment variables.

    Returns:
        Created user if created, None otherwise
    """
    from ..db.session import async_session_maker

    async with async_session_maker() as db:
        if await first_admin_exists(db):
            logger.info("First admin already exists, skipping creation")
            return None
        existing_user = await get_user_by_username(db, settings.first_admin_username)

        if existing_user:
            existing_user.is_admin = True
            existing_user.password_hash = get_password_hash(settings.first_admin_password)
            await db.commit()
            logger.info(f"Updated existing user to admin: {settings.first_admin_username}")
            return existing_user
        from ..schemas import UserCreate

        user_data = UserCreate(
            username=settings.first_admin_username,
            password=settings.first_admin_password,
        )

        user = await create_user(db, user_data, is_admin=True)

        logger.info(f"First admin created: {settings.first_admin_username}")

        return user

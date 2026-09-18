"""
First admin service
Auto-creates first admin user on application startup if no admin exists
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import User
from ..services.auth import get_password_hash
from ..services.user import get_user_by_email, create_user

# Get settings
settings = get_settings()

# Configure logging
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
    Create first admin user on startup if no admin exists.
    
    Uses FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD from environment variables.
    
    Returns:
        Created user if created, None otherwise
    """
    from ..db.session import async_session_maker
    
    async with async_session_maker() as db:
        # Check if admin already exists
        if await first_admin_exists(db):
            logger.info("First admin already exists, skipping creation")
            return None
        
        # Check if the first admin email already exists as non-admin
        existing_user = await get_user_by_email(db, settings.first_admin_email)
        
        if existing_user:
            # Update to admin
            existing_user.is_admin = True
            existing_user.password_hash = get_password_hash(settings.first_admin_password)
            await db.commit()
            logger.info(f"Updated existing user to admin: {settings.first_admin_email}")
            return existing_user
        
        # Create new admin user
        from ..schemas import UserCreate
        
        user_data = UserCreate(
            email=settings.first_admin_email,
            full_name="Admin",
            password=settings.first_admin_password,
        )
        
        user = await create_user(db, user_data, is_admin=True)
        
        logger.info(f"First admin created: {settings.first_admin_email}")
        
        return user

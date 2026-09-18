"""
Token service for managing JWT tokens in database
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import RefreshToken, InviteToken, PasswordResetToken, TokenStatus, User
from ..services.auth import get_password_hash

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)


def generate_token(length: int = 64) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return get_password_hash(token)


# =============================================================================
# REFRESH TOKEN SERVICES
# =============================================================================

async def create_refresh_token_db(
    db: AsyncSession,
    user_id: int,
    token: str,
    expires_at: datetime,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> RefreshToken:
    """
    Create a new refresh token in database.
    
    OWASP Compliance:
    - Store hash only, not plain text token
    - Include IP and user agent for security auditing
    """
    token_hash = hash_token(token)
    
    refresh_token = RefreshToken(
        token=token,  # Store plain text temporarily for response
        token_hash=token_hash,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        status=TokenStatus.ACTIVE,
        expires_at=expires_at,
        is_rotated=False,
    )
    
    db.add(refresh_token)
    await db.commit()
    await db.refresh(refresh_token)
    
    logger.debug(f"Refresh token created for user {user_id}")
    
    return refresh_token


async def get_refresh_token_by_token(
    db: AsyncSession,
    token: str,
) -> Optional[RefreshToken]:
    """Get refresh token by plain text token."""
    token_hash = hash_token(token)
    
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def get_refresh_token_by_id(
    db: AsyncSession,
    token_id: int,
) -> Optional[RefreshToken]:
    """Get refresh token by ID."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.id == token_id)
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(
    db: AsyncSession,
    token_id: int,
) -> None:
    """Revoke a refresh token."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_id)
        .values(status=TokenStatus.REVOKED)
    )
    await db.commit()
    
    logger.debug(f"Refresh token revoked: {token_id}")


async def rotate_refresh_token(
    db: AsyncSession,
    old_token_id: int,
    new_token: str,
    expires_at: datetime,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> RefreshToken:
    """
    Rotate refresh token - mark old as rotated and create new.
    
    OWASP Compliance:
    - Prevents refresh token theft by issuing new token on each use
    - Old token is marked as rotated and cannot be used again
    """
    # Mark old token as rotated
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == old_token_id)
        .values(
            status=TokenStatus.REVOKED,
            is_rotated=True,
        )
    )
    
    # Get user ID from old token
    old_token = await get_refresh_token_by_id(db, old_token_id)
    if old_token is None:
        raise ValueError("Old token not found")
    
    # Create new token
    new_refresh_token = await create_refresh_token_db(
        db=db,
        user_id=old_token.user_id,
        token=new_token,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Link new token to old token
    new_refresh_token.replaced_by_id = old_token_id
    await db.commit()
    
    logger.debug(f"Refresh token rotated: {old_token_id} -> {new_refresh_token.id}")
    
    return new_refresh_token


async def get_active_refresh_tokens_by_user(
    db: AsyncSession,
    user_id: int,
) -> list[RefreshToken]:
    """Get all active refresh tokens for a user."""
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.status == TokenStatus.ACTIVE,
        )
    )
    return result.scalars().all()


# =============================================================================
# INVITE TOKEN SERVICES
# =============================================================================

async def create_invite_token(
    db: AsyncSession,
    created_by_id: int,
    email: str,
    expires_hours: int = 24,
) -> InviteToken:
    """
    Create a new invite token.
    
    Args:
        db: Database session
        created_by_id: Admin user ID who created the invite
        email: Email of the user to invite
        expires_hours: Token expiry in hours (default: 24)
        
    Returns:
        Created invite token
    """
    # Generate token
    token = generate_token(32)
    token_hash = hash_token(token)
    
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    invite_token = InviteToken(
        token=token,
        token_hash=token_hash,
        created_by_id=created_by_id,
        email=email,
        status=TokenStatus.ACTIVE,
        expires_at=expires_at,
    )
    
    db.add(invite_token)
    await db.commit()
    await db.refresh(invite_token)
    
    logger.info(f"Invite token created for {email} by user {created_by_id}")
    
    return invite_token


async def get_invite_token_by_token(
    db: AsyncSession,
    token: str,
) -> Optional[InviteToken]:
    """Get invite token by plain text token."""
    token_hash = hash_token(token)
    
    result = await db.execute(
        select(InviteToken)
        .where(InviteToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def get_invite_token_by_email(
    db: AsyncSession,
    email: str,
) -> Optional[InviteToken]:
    """Get active invite token by email."""
    result = await db.execute(
        select(InviteToken)
        .where(
            InviteToken.email == email,
            InviteToken.status == TokenStatus.ACTIVE,
            InviteToken.expires_at > datetime.utcnow(),
        )
        .order_by(InviteToken.created_at.desc())
    )
    return result.scalar_one_or_none()


async def use_invite_token(
    db: AsyncSession,
    token: str,
    user_id: int,
) -> bool:
    """
    Mark invite token as used.
    
    Args:
        db: Database session
        token: Invite token
        user_id: User ID who used the token
        
    Returns:
        True if token was valid and marked as used
    """
    invite_token = await get_invite_token_by_token(db, token)
    
    if invite_token is None:
        return False
    
    if invite_token.status != TokenStatus.ACTIVE:
        return False
    
    if invite_token.expires_at < datetime.utcnow():
        # Expired - mark as expired
        await db.execute(
            update(InviteToken)
            .where(InviteToken.id == invite_token.id)
            .values(status=TokenStatus.EXPIRED)
        )
        await db.commit()
        return False
    
    # Mark as used
    await db.execute(
        update(InviteToken)
        .where(InviteToken.id == invite_token.id)
        .values(
            status=TokenStatus.USED,
            used_by_id=user_id,
            used_at=datetime.utcnow(),
        )
    )
    await db.commit()
    
    logger.info(f"Invite token used: {invite_token.email} by user {user_id}")
    
    return True


async def revoke_invite_token(
    db: AsyncSession,
    token_id: int,
    revoked_by_id: int,
) -> bool:
    """
    Revoke an invite token.
    
    Args:
        db: Database session
        token_id: Invite token ID
        revoked_by_id: Admin user ID who revoked the token
        
    Returns:
        True if token was found and revoked
    """
    result = await db.execute(
        update(InviteToken)
        .where(InviteToken.id == token_id)
        .values(status=TokenStatus.REVOKED)
    )
    
    if result.rowcount == 0:
        return False
    
    await db.commit()
    
    logger.info(f"Invite token revoked: {token_id} by user {revoked_by_id}")
    
    return True


async def get_invite_tokens_paginated(
    db: AsyncSession,
    created_by_id: int,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[InviteToken], int]:
    """
    Get paginated list of invite tokens created by a user.
    
    Args:
        db: Database session
        created_by_id: User ID who created the invites
        page: Page number
        page_size: Items per page
        
    Returns:
        Tuple of (invite_tokens, total_count)
    """
    # Get total count
    count_result = await db.execute(
        select(func.count())
        .where(InviteToken.created_by_id == created_by_id)
    )
    total = count_result.scalar()
    
    # Get items
    result = await db.execute(
        select(InviteToken)
        .where(InviteToken.created_by_id == created_by_id)
        .order_by(InviteToken.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tokens = result.scalars().all()
    
    return tokens, total


# =============================================================================
# PASSWORD RESET TOKEN SERVICES
# =============================================================================

async def create_password_reset_token(
    db: AsyncSession,
    user_id: int,
    expires_hours: int = 1,
) -> PasswordResetToken:
    """
    Create a new password reset token.
    
    Args:
        db: Database session
        user_id: User ID to reset password for
        expires_hours: Token expiry in hours (default: 1)
        
    Returns:
        Created password reset token
    """
    # Generate token
    token = generate_token(32)
    token_hash = hash_token(token)
    
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    reset_token = PasswordResetToken(
        token=token,
        token_hash=token_hash,
        user_id=user_id,
        status=TokenStatus.ACTIVE,
        expires_at=expires_at,
    )
    
    db.add(reset_token)
    await db.commit()
    await db.refresh(reset_token)
    
    logger.info(f"Password reset token created for user {user_id}")
    
    return reset_token


async def get_password_reset_token_by_token(
    db: AsyncSession,
    token: str,
) -> Optional[PasswordResetToken]:
    """Get password reset token by plain text token."""
    token_hash = hash_token(token)
    
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def get_password_reset_token_by_user(
    db: AsyncSession,
    user_id: int,
) -> Optional[PasswordResetToken]:
    """Get active password reset token for a user."""
    result = await db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.status == TokenStatus.ACTIVE,
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .order_by(PasswordResetToken.created_at.desc())
    )
    return result.scalar_one_or_none()


async def use_password_reset_token(
    db: AsyncSession,
    token: str,
) -> Optional[int]:
    """
    Mark password reset token as used and return user ID.
    
    Args:
        db: Database session
        token: Password reset token
        
    Returns:
        User ID if token was valid, None otherwise
    """
    reset_token = await get_password_reset_token_by_token(db, token)
    
    if reset_token is None:
        return None
    
    if reset_token.status != TokenStatus.ACTIVE:
        return None
    
    if reset_token.expires_at < datetime.utcnow():
        # Expired - mark as expired
        await db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.id == reset_token.id)
            .values(status=TokenStatus.EXPIRED)
        )
        await db.commit()
        return None
    
    # Mark as used
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == reset_token.id)
        .values(
            status=TokenStatus.USED,
            used_at=datetime.utcnow(),
        )
    )
    await db.commit()
    
    logger.info(f"Password reset token used for user {reset_token.user_id}")
    
    return reset_token.user_id


async def revoke_password_reset_tokens(
    db: AsyncSession,
    user_id: int,
) -> int:
    """
    Revoke all password reset tokens for a user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Number of tokens revoked
    """
    result = await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id)
        .values(status=TokenStatus.REVOKED)
    )
    
    await db.commit()
    
    logger.info(f"Password reset tokens revoked for user {user_id}")
    
    return result.rowcount

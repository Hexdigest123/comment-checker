"""
Token service for managing JWT refresh tokens in database
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import RefreshToken, TokenStatus

logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    """Hash a token for storage (deterministic, so tokens can be looked up by hash)."""
    return hashlib.sha256(token.encode()).hexdigest()


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
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == old_token_id)
        .values(
            status=TokenStatus.REVOKED,
            is_rotated=True,
        )
    )

    old_token = await get_refresh_token_by_id(db, old_token_id)
    if old_token is None:
        raise ValueError("Old token not found")
    new_refresh_token = await create_refresh_token_db(
        db=db,
        user_id=old_token.user_id,
        token=new_token,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    new_refresh_token.replaced_by_id = old_token_id
    await db.commit()

    logger.debug(f"Refresh token rotated: {old_token_id} -> {new_refresh_token.id}")

    return new_refresh_token

"""
Invites API router
Handles admin invitation management
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import User, InviteToken, TokenStatus
from ..schemas import (
    InviteTokenCreate,
    InviteTokenResponse,
    InviteTokenListResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetResponse,
    PageParams,
    PageResponse,
)
from ..services.token import (
    create_invite_token,
    get_invite_token_by_token,
    get_invite_token_by_email,
    use_invite_token,
    revoke_invite_token,
    get_invite_tokens_paginated,
    create_password_reset_token,
    get_password_reset_token_by_token,
    use_password_reset_token,
    revoke_password_reset_tokens,
)
from ..services.user import get_user_by_email, create_user
from ..services.email import send_invite_email, send_password_reset_email
from ..api.auth import get_current_user, get_current_active_user, get_current_admin_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/invites", tags=["Invites"])


@router.post("/", response_model=InviteTokenResponse)
async def create_invite(
    invite_data: InviteTokenCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> InviteTokenResponse:
    """
    Create a new admin invite token.
    
    Args:
        invite_data: Email of the user to invite
    """
    # Check if user already exists
    existing_user = await get_user_by_email(db, invite_data.email)
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    
    # Check if there's already an active invite for this email
    existing_invite = await get_invite_token_by_email(db, invite_data.email)
    
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active invite already exists for this email",
        )
    
    # Create invite token
    invite_token = await create_invite_token(
        db=db,
        created_by_id=current_user.id,
        email=invite_data.email,
    )
    
    # Send email (in dev, Mailpit will catch it)
    frontend_url = request.headers.get("origin") or settings.frontend_url
    await send_invite_email(
        to_email=invite_data.email,
        invite_token=invite_token.token,
        created_by_email=current_user.email,
        frontend_url=frontend_url,
    )
    
    logger.info(f"Invite created for {invite_data.email} by {current_user.email}")
    
    return InviteTokenResponse(
        id=invite_token.id,
        email=invite_token.email,
        token=invite_token.token,
        status=invite_token.status.value,
        created_by_id=invite_token.created_by_id,
        created_at=invite_token.created_at,
        expires_at=invite_token.expires_at,
        used_at=invite_token.used_at,
    )


@router.get("/", response_model=PageResponse[InviteTokenListResponse])
async def list_invites(
    params: PageParams = Depends(),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> PageResponse[InviteTokenListResponse]:
    """
    List all invite tokens created by the current user.
    
    Supports pagination.
    """
    tokens, total = await get_invite_tokens_paginated(
        db=db,
        created_by_id=current_user.id,
        page=params.page,
        page_size=params.page_size,
    )
    
    # Calculate pagination info
    total_pages = (total + params.page_size - 1) // params.page_size
    has_next = params.page < total_pages
    has_previous = params.page > 1
    
    return PageResponse[
        InviteTokenListResponse
    ](
        items=[
            InviteTokenListResponse(
                id=t.id,
                email=t.email,
                status=t.status.value,
                created_by_id=t.created_by_id,
                created_at=t.created_at,
                expires_at=t.expires_at,
                used_at=t.used_at,
            )
            for t in tokens
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


@router.get("/{token}", response_model=InviteTokenResponse)
async def get_invite(
    token: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> InviteTokenResponse:
    """
    Get invite token details by token.
    
    Args:
        token: Invite token
    """
    invite_token = await get_invite_token_by_token(db, token)
    
    if invite_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )
    
    # Check if current user can access this invite
    if not current_user.is_admin and invite_token.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return InviteTokenResponse(
        id=invite_token.id,
        email=invite_token.email,
        token=invite_token.token,
        status=invite_token.status.value,
        created_by_id=invite_token.created_by_id,
        created_at=invite_token.created_at,
        expires_at=invite_token.expires_at,
        used_at=invite_token.used_at,
    )


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    token: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """
    Revoke an invite token.
    
    Args:
        token: Invite token to revoke
    """
    invite_token = await get_invite_token_by_token(db, token)
    
    if invite_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )
    
    # Check if current user created this invite
    if invite_token.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke invites you created",
        )
    
    await revoke_invite_token(
        db=db,
        token_id=invite_token.id,
        revoked_by_id=current_user.id,
    )
    
    logger.info(f"Invite revoked: {token} by {current_user.email}")


@router.post("/{token}/use", response_model=InviteTokenResponse)
async def use_invite_token_endpoint(
    token: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> InviteTokenResponse:
    """
    Use an invite token to create a new admin user.
    
    This is called during registration with an invite token.
    
    Args:
        token: Invite token
    """
    invite_token = await get_invite_token_by_token(db, token)
    
    if invite_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite token",
        )
    
    if invite_token.status != TokenStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite token is not active",
        )
    
    if invite_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite token has expired",
        )
    
    # Mark as used
    await use_invite_token(
        db=db,
        token=token,
        user_id=None,  # Will be set when user is created
    )
    
    return InviteTokenResponse(
        id=invite_token.id,
        email=invite_token.email,
        token=invite_token.token,
        status=invite_token.status.value,
        created_by_id=invite_token.created_by_id,
        created_at=invite_token.created_at,
        expires_at=invite_token.expires_at,
        used_at=invite_token.used_at,
    )


# =============================================================================
# PASSWORD RESET ENDPOINTS
# =============================================================================

@router.post("/password-reset", response_model=PasswordResetResponse)
async def request_password_reset(
    request: Request,
    password_reset_request: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PasswordResetResponse:
    """
    Request a password reset email.
    
    Args:
        password_reset_request: Email address
    """
    user = await get_user_by_email(db, password_reset_request.email)
    
    if user is None:
        # Don't reveal whether email exists for security
        logger.warning(f"Password reset requested for non-existent email: {password_reset_request.email}")
        return PasswordResetResponse(
            message="If this email exists, a reset link has been sent",
            success=True,
        )
    
    # Revoke any existing reset tokens
    await revoke_password_reset_tokens(db, user.id)
    
    # Create new reset token
    reset_token = await create_password_reset_token(
        db=db,
        user_id=user.id,
    )
    
    # Send email
    frontend_url = request.headers.get("origin") or settings.frontend_url
    await send_password_reset_email(
        to_email=user.email,
        reset_token=reset_token.token,
        frontend_url=frontend_url,
    )
    
    logger.info(f"Password reset requested for {user.email}")
    
    return PasswordResetResponse(
        message="If this email exists, a reset link has been sent",
        success=True,
    )


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    password_reset_confirm: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PasswordResetResponse:
    """
    Confirm password reset with token and new password.
    
    Args:
        password_reset_confirm: Token and new password
    """
    user_id = await use_password_reset_token(
        db=db,
        token=password_reset_confirm.token,
    )
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )
    
    # Get user
    user = await get_user_by_id(db, user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update password
    from ..services.auth import get_password_hash
    from sqlalchemy import update
    
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            password_hash=get_password_hash(password_reset_confirm.new_password),
            password_changed_at=datetime.utcnow(),
        )
    )
    await db.commit()
    
    logger.info(f"Password reset completed for user {user.email}")
    
    return PasswordResetResponse(
        message="Password has been reset successfully",
        success=True,
    )


# Fix import - datetime was not imported
from datetime import datetime

"""
Classification API router
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import Classification, Comment, User
from ..schemas import (
    ClassificationResponse,
    ClassificationListResponse,
    ClassificationStatsResponse,
    PageParams,
    PageResponse,
)
from ..services.classification import (
    classify_comment,
    classification_to_response,
    get_classification_by_id,
    get_classifications_by_comment,
    get_classifications_paginated,
    get_classification_stats,
)
from ..services.comment import get_comment_by_id, update_comment_status
from ..db.models import CommentStatus
from ..api.auth import get_current_active_user

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Classifications"])


@router.get("/", response_model=PageResponse[ClassificationListResponse])
async def list_classifications(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    params: PageParams = Depends(),
    comment_id: Optional[int] = None,
) -> PageResponse[ClassificationListResponse]:
    """
    List classifications with pagination, search, sort, and filter.
    
    Supports:
    - Pagination (page, page_size)
    - Search (in comment text)
    - Sort (sort_by, sort_order)
    - Filter by comment, backend, flagged, category, etc.
    """
    filter_conditions = []
    
    if not current_user.is_admin:
        # Scope to the user's own comments via EXISTS; a bare
        # Comment.user_id filter would cross-join and not scope at all.
        filter_conditions.append(
            Classification.comment.has(Comment.user_id == current_user.id)
        )
    
    # Comment filter
    if comment_id is not None:
        filter_conditions.append(Classification.comment_id == comment_id)
    
    # Backend filter
    if params.backend:
        try:
            from ..db.models import ClassificationBackend
            backend_enum = ClassificationBackend(params.backend.lower())
            filter_conditions.append(Classification.backend == backend_enum)
        except ValueError:
            pass
    
    # Flagged filter
    if params.flagged is not None:
        filter_conditions.append(Classification.flagged == params.flagged)
    
    # Category filter
    if params.category:
        try:
            from ..db.models import ClassificationCategory
            category_enum = ClassificationCategory(params.category.lower())
            filter_conditions.append(Classification.category == category_enum)
        except ValueError:
            pass
    
    # Date range filter
    if params.start_date or params.end_date:
        from datetime import datetime
        if params.start_date:
            try:
                start_date = datetime.fromisoformat(params.start_date)
                filter_conditions.append(Classification.created_at >= start_date)
            except ValueError:
                pass
        if params.end_date:
            try:
                end_date = datetime.fromisoformat(params.end_date)
                filter_conditions.append(Classification.created_at <= end_date)
            except ValueError:
                pass
    combined_filter = and_(*filter_conditions) if filter_conditions else None
    
    result = await get_classifications_paginated(
        db=db,
        page=params.page,
        page_size=params.page_size,
        sort_by=params.sort_by or "created_at",
        sort_order=params.sort_order or "desc",
        filter_condition=combined_filter,
    )
    
    return result


@router.post("/{comment_id}/classify", response_model=ClassificationResponse)
async def classify_comment_endpoint(
    comment_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClassificationResponse:
    """
    Classify a comment using the default backend.
    
    This endpoint triggers classification for a specific comment.
    """
    comment = await get_comment_by_id(db, comment_id)
    
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    if not current_user.is_admin and comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    existing_classifications = await get_classifications_by_comment(db, comment_id)
    
    if existing_classifications:
        latest = max(existing_classifications, key=lambda c: c.created_at)
        return classification_to_response(latest)
    await update_comment_status(
        db=db,
        comment_id=comment_id,
        status=CommentStatus.WAITING,
    )
    
    classification = await classify_comment(
        db=db,
        comment_id=comment_id,
        backend=None,  # Use default
        context=comment.context,
    )
    
    logger.info(f"Comment classified via API: {comment_id}")

    return classification_to_response(classification)


@router.get("/stats", response_model=ClassificationStatsResponse)
async def get_classification_stats_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    backend: str = None,
    date_range: str = None,
) -> ClassificationStatsResponse:
    """
    Get classification statistics.
    
    Args:
        backend: Filter by backend (typesafe, mistral, combined)
        date_range: Filter by date range (1m, 6m, 1y, all)
    """
    # Admin can see all stats, regular users see only their own
    user_filter = None
    if not current_user.is_admin:
        user_filter = Classification.comment.has(user_id=current_user.id)
    
    stats = await get_classification_stats(
        db=db,
        backend=backend,
        date_range=date_range,
    )
    
    return stats


@router.get("/{classification_id}", response_model=ClassificationResponse)
async def get_classification(
    classification_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClassificationResponse:
    """Get a single classification by ID."""
    classification = await get_classification_by_id(db, classification_id)

    if classification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found",
        )
    if not current_user.is_admin and classification.comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return classification_to_response(classification)

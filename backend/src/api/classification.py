"""
Classification API router
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_

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
    classify_comment_batch,
    get_classification_by_id,
    get_classifications_by_comment,
    get_classifications_paginated,
    get_classification_stats,
)
from ..services.comment import get_comment_by_id, update_comment_status
from ..db.models import CommentStatus
from ..api.auth import get_current_user, get_current_active_user, get_current_admin_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/classifications", tags=["Classifications"])


@router.get("/", response_model=PageResponse[ClassificationListResponse])
async def list_classifications(
    params: PageParams = Depends(),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PageResponse[ClassificationListResponse]:
    """
    List classifications with pagination, search, sort, and filter.
    
    Supports:
    - Pagination (page, page_size)
    - Search (in comment text)
    - Sort (sort_by, sort_order)
    - Filter by backend, flagged, category, etc.
    """
    # Build filter conditions
    filter_conditions = []
    
    # User filter (admin can see all, regular users see only their own comments)
    if not current_user.is_admin:
        filter_conditions.append(Comment.user_id == current_user.id)
    
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
    
    # Combine all conditions
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


@router.get("/{classification_id}", response_model=ClassificationResponse)
async def get_classification(
    classification_id: int,
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
    
    # Check access
    if not current_user.is_admin and classification.comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return ClassificationResponse(
        id=classification.id,
        comment_id=classification.comment_id,
        backend=classification.backend.value,
        flagged=classification.flagged,
        flagged_by=classification.flagged_by,
        category=classification.category.value if classification.category else None,
        category_label=classification.category_label,
        scores=classification.scores,
        confidence=classification.confidence,
        severity=classification.severity.value if classification.severity else None,
        severity_label=classification.severity_label,
        harmful=classification.harmful,
        threshold=classification.threshold,
        processing_time_ms=classification.processing_time_ms,
        created_at=classification.created_at,
    )


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
    # Get comment
    comment = await get_comment_by_id(db, comment_id)
    
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    
    # Check access
    if not current_user.is_admin and comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Check if already classified
    existing_classifications = await get_classifications_by_comment(db, comment_id)
    
    if existing_classifications:
        # Return the most recent classification
        latest = max(existing_classifications, key=lambda c: c.created_at)
        return ClassificationResponse(
            id=latest.id,
            comment_id=latest.comment_id,
            backend=latest.backend.value,
            flagged=latest.flagged,
            flagged_by=latest.flagged_by,
            category=latest.category.value if latest.category else None,
            category_label=latest.category_label,
            scores=latest.scores,
            confidence=latest.confidence,
            severity=latest.severity.value if latest.severity else None,
            severity_label=latest.severity_label,
            harmful=latest.harmful,
            threshold=latest.threshold,
            processing_time_ms=latest.processing_time_ms,
            created_at=latest.created_at,
        )
    
    # Update comment status
    await update_comment_status(
        db=db,
        comment_id=comment_id,
        status=CommentStatus.WAITING,
    )
    
    # Classify
    classification = await classify_comment(
        db=db,
        comment_id=comment_id,
        backend=None,  # Use default
        context=comment.context,
    )
    
    logger.info(f"Comment classified via API: {comment_id}")
    
    return ClassificationResponse(
        id=classification.id,
        comment_id=classification.comment_id,
        backend=classification.backend.value,
        flagged=classification.flagged,
        flagged_by=classification.flagged_by,
        category=classification.category.value if classification.category else None,
        category_label=classification.category_label,
        scores=classification.scores,
        confidence=classification.confidence,
        severity=classification.severity.value if classification.severity else None,
        severity_label=classification.severity_label,
        harmful=classification.harmful,
        threshold=classification.threshold,
        processing_time_ms=classification.processing_time_ms,
        created_at=classification.created_at,
    )


@router.get("/stats", response_model=ClassificationStatsResponse)
async def get_classification_stats_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    backend: str = None,
    date_range: str = None,
    current_user: Annotated[User, Depends(get_current_active_user)],
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

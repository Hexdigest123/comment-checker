"""
Comments API router
"""

import logging
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, desc, asc

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import Comment, CommentStatus, CommentPriority, User
from ..schemas import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentListResponse,
    CommentUploadResponse,
    CommentStatusResponse,
    PageParams,
    PageResponse,
    CSVUploadResponse,
)
from ..services.comment import (
    get_comment_by_id,
    get_comments_by_user,
    create_comment,
    update_comment,
    delete_comment,
    get_comments_paginated,
)
from ..services.csv_processor import process_csv_file
from ..api.auth import get_current_user, get_current_active_user, get_current_admin_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/comments", tags=["Comments"])


@router.get("/", response_model=PageResponse[CommentListResponse])
async def list_comments(
    params: PageParams = Depends(),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PageResponse[CommentListResponse]:
    """
    List comments with pagination, search, sort, and filter.
    
    Supports:
    - Pagination (page, page_size)
    - Search (search term in text, author, url)
    - Sort (sort_by, sort_order)
    - Filter by status, user, date range, etc.
    """
    # Build filter conditions
    filter_conditions = []
    
    # Status filter
    if params.status:
        try:
            status_enum = CommentStatus(params.status.lower())
            filter_conditions.append(Comment.status == status_enum)
        except ValueError:
            pass
    
    # User filter (admin can see all, regular users see only their own)
    if not current_user.is_admin:
        filter_conditions.append(Comment.user_id == current_user.id)
    elif params.search and "user:" in params.search:
        # Extract user ID from search
        import re
        match = re.search(r"user:(\d+)", params.search)
        if match:
            filter_conditions.append(Comment.user_id == int(match.group(1)))
    
    # Date range filter
    if params.start_date:
        try:
            start_date = datetime.fromisoformat(params.start_date)
            filter_conditions.append(Comment.created_at >= start_date)
        except ValueError:
            pass
    
    if params.end_date:
        try:
            end_date = datetime.fromisoformat(params.end_date)
            filter_conditions.append(Comment.created_at <= end_date)
        except ValueError:
            pass
    
    # Search filter
    if params.search:
        search_pattern = f"%{params.search}%"
        search_conditions = [
            Comment.text.ilike(search_pattern),
        ]
        if current_user.is_admin:
            search_conditions.extend([
                Comment.original_author.ilike(search_pattern),
                Comment.source_url.ilike(search_pattern),
            ])
        filter_conditions.append(or_(*search_conditions))
    
    # Combine all conditions
    combined_filter = and_(*filter_conditions) if filter_conditions else None
    
    result = await get_comments_paginated(
        db=db,
        page=params.page,
        page_size=params.page_size,
        sort_by=params.sort_by or "created_at",
        sort_order=params.sort_order or "desc",
        filter_condition=combined_filter,
    )
    
    return result


@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentResponse:
    """Get a single comment by ID."""
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
    
    return CommentResponse(
        id=comment.id,
        text=comment.text,
        original_author=comment.original_author,
        original_author_id=comment.original_author_id,
        original_author_url=comment.original_author_url,
        source_url=comment.source_url,
        source_platform=comment.source_platform,
        context=comment.context,
        user_id=comment.user_id,
        status=comment.status.value,
        priority=comment.priority.value,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
        metadata=comment.metadata,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        classifications=[
            {
                "id": c.id,
                "backend": c.backend.value,
                "flagged": c.flagged,
                "flagged_by": c.flagged_by,
                "category": c.category.value if c.category else None,
                "category_label": c.category_label,
                "scores": c.scores,
                "confidence": c.confidence,
                "severity": c.severity.value if c.severity else None,
                "severity_label": c.severity_label,
                "harmful": c.harmful,
                "threshold": c.threshold,
                "created_at": c.created_at,
            }
            for c in comment.classifications
        ] if comment.classifications else None,
    )


@router.post("/", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment_endpoint(
    comment_create: CommentCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentResponse:
    """Create a new comment."""
    # Set user_id to current user
    comment_data = comment_create.model_dump()
    comment_data["user_id"] = current_user.id
    
    # Set priority
    if comment_create.priority:
        try:
            comment_data["priority"] = CommentPriority(comment_create.priority.lower())
        except ValueError:
            comment_data["priority"] = CommentPriority.MEDIUM
    else:
        comment_data["priority"] = CommentPriority.MEDIUM
    
    comment = await create_comment(db, comment_data)
    
    return CommentResponse(
        id=comment.id,
        text=comment.text,
        original_author=comment.original_author,
        original_author_id=comment.original_author_id,
        original_author_url=comment.original_author_url,
        source_url=comment.source_url,
        source_platform=comment.source_platform,
        context=comment.context,
        user_id=comment.user_id,
        status=comment.status.value,
        priority=comment.priority.value,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
        metadata=comment.metadata,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        classifications=None,
    )


@router.post("/upload", response_model=CSVUploadResponse)
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CSVUploadResponse:
    """
    Upload CSV file with comments to classify.
    
    Processes the CSV file and queues comments for classification.
    """
    # Validate file size
    max_size_mb = settings.max_csv_size_mb
    max_size_bytes = max_size_mb * 1024 * 1024
    
    # Read file content to check size
    content = await file.read()
    
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_size_mb}MB",
        )
    
    # Reset file pointer
    file.file.seek(0)
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Process CSV file
    result = await process_csv_file(
        db=db,
        file=file,
        user_id=current_user.id,
        batch_id=batch_id,
    )
    
    logger.info(f"CSV uploaded by user {current_user.id}: {result['valid_rows']} valid rows, {result['invalid_rows']} invalid rows")
    
    return CSVUploadResponse(
        message="CSV file uploaded successfully",
        batch_id=batch_id,
        total_rows=result["total_rows"],
        valid_rows=result["valid_rows"],
        invalid_rows=result["invalid_rows"],
        processing=True,
    )


@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment_endpoint(
    comment_id: int,
    comment_update: CommentUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentResponse:
    """Update a comment."""
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
    
    comment = await update_comment(db, comment_id, comment_update)
    
    return CommentResponse(
        id=comment.id,
        text=comment.text,
        original_author=comment.original_author,
        original_author_id=comment.original_author_id,
        original_author_url=comment.original_author_url,
        source_url=comment.source_url,
        source_platform=comment.source_platform,
        context=comment.context,
        user_id=comment.user_id,
        status=comment.status.value,
        priority=comment.priority.value,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
        metadata=comment.metadata,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        classifications=[
            {
                "id": c.id,
                "backend": c.backend.value,
                "flagged": c.flagged,
                "flagged_by": c.flagged_by,
                "category": c.category.value if c.category else None,
                "category_label": c.category_label,
                "scores": c.scores,
                "confidence": c.confidence,
                "severity": c.severity.value if c.severity else None,
                "severity_label": c.severity_label,
                "harmful": c.harmful,
                "threshold": c.threshold,
                "created_at": c.created_at,
            }
            for c in comment.classifications
        ] if comment.classifications else None,
    )


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment_endpoint(
    comment_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete a comment."""
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
    
    await delete_comment(db, comment_id)
    
    logger.info(f"Comment deleted: {comment_id}")


@router.get("/{comment_id}/status", response_model=CommentStatusResponse)
async def get_comment_status(
    comment_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentStatusResponse:
    """Get comment processing status."""
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
    
    return CommentStatusResponse(
        id=comment.id,
        status=comment.status.value,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
    )

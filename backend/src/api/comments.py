"""
Comments API router
"""

import logging
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, File, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_, select

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import (
    Comment,
    CommentStatus,
    CommentPriority,
    ExternalAccount,
    User,
    Classification,
    ClassificationCategory,
    ClassificationSeverity,
)
from ..schemas import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentListResponse,
    CommentMentionResponse,
    CommentSearchResponse,
    CommentVoteResponse,
    CommentStatusResponse,
    PageParams,
    PageResponse,
    CSVUploadResponse,
)
from ..services.comment import (
    get_comment_by_id,
    create_comment,
    update_comment,
    delete_comment,
    get_comments_paginated,
)
from ..services.classification import classification_to_response
from ..services.csv_processor import process_csv_file
from ..api.auth import get_current_active_user

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Comments"])


def _platform_value(platform) -> Optional[str]:
    """Return the string value of a platform enum member or None."""
    if platform is None:
        return None
    return str(platform.value) if hasattr(platform, "value") else str(platform)


def _mentions_response(comment: Comment) -> Optional[list[CommentMentionResponse]]:
    """Build mention response models for a comment with loaded mentions."""
    if not comment.mentions:
        return None
    return [
        CommentMentionResponse(
            account_id=m.external_account.id,
            username=m.external_account.username,
            display_name=m.external_account.display_name,
            platform=_platform_value(m.external_account.platform),
            profile_url=m.external_account.profile_url,
            cluster_id=m.external_account.cluster_id,
            mentioned_username=m.mentioned_username,
        )
        for m in comment.mentions
    ]


@router.get("/", response_model=PageResponse[CommentListResponse])
async def list_comments(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    params: PageParams = Depends(),
    account_id: Optional[str] = Query(None, description="Filter by external account ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID (comments from its accounts)"),
) -> PageResponse[CommentListResponse]:
    """
    List comments with pagination, search, sort, and filter.
    
    Supports:
    - Pagination (page, page_size)
    - Search (search term in text, author, url)
    - Sort (sort_by, sort_order)
    - Filter by status, user, date range, etc.
    """
    filter_conditions = []
    
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

    # Classification filters: comments having at least one
    # classification with the requested category/severity
    if params.category:
        try:
            category_enum = ClassificationCategory(params.category.lower())
            filter_conditions.append(
                Comment.id.in_(
                    select(Classification.comment_id).where(
                        Classification.category == category_enum
                    )
                )
            )
        except ValueError:
            pass

    if params.severity:
        try:
            severity_enum = ClassificationSeverity(params.severity.lower())
            filter_conditions.append(
                Comment.id.in_(
                    select(Classification.comment_id).where(
                        Classification.severity == severity_enum
                    )
                )
            )
        except ValueError:
            pass

    # Entity graph filters: comments authored by an account, or by any account in a cluster
    if account_id:
        filter_conditions.append(Comment.external_account_id == account_id)

    if cluster_id:
        filter_conditions.append(
            Comment.external_account_id.in_(
                select(ExternalAccount.id).where(ExternalAccount.cluster_id == cluster_id)
            )
        )

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
    if filter_conditions:
        combined_filter = and_(*filter_conditions) if len(filter_conditions) > 1 else filter_conditions[0]
    else:
        combined_filter = None
    
    result = await get_comments_paginated(
        db=db,
        page=params.page,
        page_size=params.page_size,
        sort_by=params.sort_by or "created_at",
        sort_order=params.sort_order or "desc",
        filter_condition=combined_filter,
    )
    
    return result


@router.get("/search/semantic", response_model=list[CommentSearchResponse])
async def semantic_comment_search(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    query: str = Query(..., min_length=1, description="Natural language search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="Minimum similarity score"),
) -> list[CommentSearchResponse]:
    """
    Semantic search over comments using Mistral embeddings.

    Finds comments whose meaning is closest to the query, even without
    matching keywords. Each result includes a similarity score (0-1).
    """
    from ..services.embedding import EmbeddingService

    embedding_service = EmbeddingService(db)
    results = await embedding_service.semantic_search(
        query=query,
        limit=limit,
        min_similarity=min_similarity,
    )
    await embedding_service.close()

    # Regular users only see their own comments
    items = []
    for comment, similarity in results:
        if not current_user.is_admin and comment.user_id != current_user.id:
            continue
        items.append(
            CommentSearchResponse(
                id=comment.id,
                text=comment.text,
                original_author=comment.original_author,
                source_url=comment.source_url,
                source_platform=comment.source_platform,
                status=comment.status.value if hasattr(comment.status, "value") else comment.status,
                similarity=round(similarity, 4),
                created_at=comment.created_at,
            )
        )
    return items


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
        status=comment.status.value if hasattr(comment.status, "value") else comment.status,
        priority=comment.priority.value if hasattr(comment.priority, "value") else comment.priority,
        vote_score=comment.vote_score,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
        metadata=comment.extra_metadata,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        classifications=[
            classification_to_response(c).model_dump(mode="json")
            for c in comment.classifications
        ] if comment.classifications else None,
        mentions=_mentions_response(comment),
    )


@router.post("/", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment_endpoint(
    comment_create: CommentCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentResponse:
    """Create a new comment."""
    comment_data = comment_create.model_dump()
    comment_data["user_id"] = current_user.id
    
    if comment_create.priority:
        try:
            comment_data["priority"] = CommentPriority(comment_create.priority.lower())
        except ValueError:
            comment_data["priority"] = CommentPriority.MEDIUM
    else:
        comment_data["priority"] = CommentPriority.MEDIUM
    
    comment = await create_comment(db, comment_data)

    # Re-fetch with mentions loaded for the response
    comment = await get_comment_by_id(db, comment.id)

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
        vote_score=comment.vote_score,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
        metadata=comment.extra_metadata,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        classifications=None,
        mentions=_mentions_response(comment),
    )


@router.post("/upload", response_model=CSVUploadResponse)
async def upload_csv(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    file: UploadFile = File(...),
    context: Optional[str] = Form(
        default=None,
        description="Context the comments react to (used for classification)",
    ),
) -> CSVUploadResponse:
    """
    Upload CSV file with comments to classify.
    
    Processes the CSV file and queues comments for classification.
    """
    max_size_mb = settings.max_csv_size_mb
    max_size_bytes = max_size_mb * 1024 * 1024
    
    content = await file.read()
    
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_size_mb}MB",
        )
    
    # Reset file pointer
    file.file.seek(0)
    batch_id = str(uuid.uuid4())
    
    result = await process_csv_file(
        db=db,
        file=file,
        user_id=current_user.id,
        batch_id=batch_id,
        default_context=context,
    )
    
    logger.info(
        f"CSV uploaded by user {current_user.id}: "
        f"{result['valid_rows']} valid rows, {result['invalid_rows']} invalid rows, "
        f"{result['duplicates_skipped']} duplicates skipped"
    )
    
    return CSVUploadResponse(
        message="CSV file uploaded successfully",
        batch_id=batch_id,
        total_rows=result["total_rows"],
        valid_rows=result["valid_rows"],
        invalid_rows=result["invalid_rows"],
        duplicates_skipped=result["duplicates_skipped"],
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
    if not current_user.is_admin and comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    comment = await update_comment(db, comment_id, comment_update)

    # Re-fetch with mentions loaded for the response
    comment = await get_comment_by_id(db, comment.id)

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
        status=comment.status.value if hasattr(comment.status, "value") else comment.status,
        priority=comment.priority.value if hasattr(comment.priority, "value") else comment.priority,
        vote_score=comment.vote_score,
        processed_at=comment.processed_at,
        processing_started_at=comment.processing_started_at,
        error_message=comment.error_message,
        metadata=comment.extra_metadata,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        classifications=[
            classification_to_response(c).model_dump(mode="json")
            for c in comment.classifications
        ] if comment.classifications else None,
        mentions=_mentions_response(comment),
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


@router.post("/{comment_id}/upvote", response_model=CommentVoteResponse)
async def upvote_comment(
    comment_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentVoteResponse:
    """Upvote a comment (raises its vote score by one)."""
    return await _vote_comment(db, current_user, comment_id, +1)


@router.post("/{comment_id}/downvote", response_model=CommentVoteResponse)
async def downvote_comment(
    comment_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CommentVoteResponse:
    """Downvote a comment (lowers its vote score by one; below 0 = false flag)."""
    return await _vote_comment(db, current_user, comment_id, -1)


async def _vote_comment(
    db: AsyncSession,
    current_user: User,
    comment_id: int,
    delta: int,
) -> CommentVoteResponse:
    """Apply a vote (+1/-1) to a comment and return the new score."""
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

    comment.vote_score = comment.vote_score + delta
    await db.commit()
    await db.refresh(comment)

    logger.info(f"Comment {comment_id} voted ({'up' if delta > 0 else 'down'}): score={comment.vote_score}")

    return CommentVoteResponse(
        id=comment.id,
        vote_score=comment.vote_score,
        false_flag=comment.is_false_flag,
    )

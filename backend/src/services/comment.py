"""
Comment service
Uses the new DB models for comment operations
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select, update, delete, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..db.models import Comment
from ..db.models.comment import CommentStatus as CS, CommentPriority as CP
from ..schemas import CommentUpdate, PageResponse, CommentListResponse

logger = logging.getLogger(__name__)


async def get_comment_by_id(
    db: AsyncSession,
    comment_id: str,
) -> Optional[Comment]:
    """Get comment by ID with classifications and external account."""
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment_id)
        .options(
            joinedload(Comment.classifications),
            joinedload(Comment.user),
            joinedload(Comment.external_account)
        )
    )
    return result.unique().scalar_one_or_none()


async def get_comments_by_user(
    db: AsyncSession,
    user_id: str,
    limit: int = 100,
) -> List[Comment]:
    """Get comments by user ID."""
    result = await db.execute(
        select(Comment)
        .where(Comment.user_id == user_id)
        .order_by(desc(Comment.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def create_comment(
    db: AsyncSession,
    comment_data: Dict[str, Any],
) -> Comment:
    """
    Create a new comment.
    
    Args:
        db: Database session
        comment_data: Comment data dictionary
        
    Returns:
        Created comment
    """
    user_id = comment_data.get("user_id")
    if user_id is not None and isinstance(user_id, int):
        user_id = str(user_id)
    
    priority = comment_data.get("priority")
    if priority:
        if isinstance(priority, str):
            try:
                priority = CP(priority.lower())
            except ValueError:
                priority = CP.MEDIUM
    else:
        priority = CP.MEDIUM
    status = comment_data.get("status")
    if status:
        if isinstance(status, str):
            try:
                status = CS(status.lower())
            except ValueError:
                status = CS.PENDING
    else:
        status = CS.PENDING

    comment = Comment(
        id=comment_data.get("id"),
        text=comment_data.get("text"),
        user_id=comment_data.get("user_id"),
        external_account_id=comment_data.get("external_account_id"),
        platform=comment_data.get("platform"),
        platform_comment_id=comment_data.get("platform_comment_id"),
        original_author=comment_data.get("original_author"),
        source_platform=comment_data.get("source_platform"),
        source_url=comment_data.get("source_url"),
        context=comment_data.get("context"),
        priority=priority,
        status=status,
        extra_metadata=comment_data.get("metadata", {}),
    )
    
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    logger.info(f"Comment created: {comment.id}")
    
    return comment


async def create_comment_batch(
    db: AsyncSession,
    comments_data: List[Dict[str, Any]],
) -> List[Comment]:
    """
    Create multiple comments in a batch.
    
    Args:
        db: Database session
        comments_data: List of comment data dictionaries
        
    Returns:
        List of created comments
    """
    comments = []
    
    for comment_data in comments_data:
        user_id = comment_data.get("user_id")
        if user_id is not None and isinstance(user_id, int):
            user_id = str(user_id)
        
        priority = comment_data.get("priority")
        if priority:
            if isinstance(priority, str):
                try:
                    priority = CP(priority.lower())
                except ValueError:
                    priority = CP.MEDIUM
        else:
            priority = CP.MEDIUM
        status = comment_data.get("status")
        if status:
            if isinstance(status, str):
                try:
                    status = CS(status.lower())
                except ValueError:
                    status = CS.PENDING
        else:
            status = CS.PENDING

        comment = Comment(
            text=comment_data.get("text"),
            user_id=comment_data.get("user_id"),
            external_account_id=comment_data.get("external_account_id"),
            platform=comment_data.get("platform"),
            platform_comment_id=comment_data.get("platform_comment_id"),
            original_author=comment_data.get("original_author"),
            source_platform=comment_data.get("source_platform"),
            source_url=comment_data.get("source_url"),
            context=comment_data.get("context"),
            priority=priority,
            status=status,
            extra_metadata=comment_data.get("metadata", {}),
        )
        comments.append(comment)
    
    db.add_all(comments)
    await db.commit()
    
    for comment in comments:
        await db.refresh(comment)
    
    logger.info(f"Batch of {len(comments)} comments created")
    
    return comments


async def update_comment(
    db: AsyncSession,
    comment_id: str,
    comment_update: CommentUpdate,
) -> Comment:
    """
    Update a comment.
    
    Args:
        db: Database session
        comment_id: Comment ID to update
        comment_update: Comment update data
        
    Returns:
        Updated comment
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    
    if comment is None:
        raise ValueError("Comment not found")
    if comment_update.text:
        comment.text = comment_update.text
    
    if comment_update.original_author:
        comment.original_author = comment_update.original_author
    
    if comment_update.source_url:
        comment.source_url = comment_update.source_url
    
    if comment_update.context:
        comment.context = comment_update.context
    
    if comment_update.priority:
        try:
            comment.priority = CP(comment_update.priority.lower())
        except ValueError:
            comment.priority = CP.MEDIUM
    
    if comment_update.metadata:
        comment.extra_metadata = comment_update.metadata
    
    comment.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(comment)
    
    logger.info(f"Comment updated: {comment.id}")
    
    return comment


async def delete_comment(
    db: AsyncSession,
    comment_id: str,
) -> None:
    """
    Delete a comment and all related classifications.
    
    Args:
        db: Database session
        comment_id: Comment ID to delete
    """
    result = await db.execute(
        delete(Comment).where(Comment.id == comment_id)
    )
    
    if result.rowcount == 0:
        raise ValueError("Comment not found")
    
    await db.commit()
    
    logger.info(f"Comment deleted: {comment_id}")


async def update_comment_status(
    db: AsyncSession,
    comment_id: str,
    status: str,
    error_message: Optional[str] = None,
    processing_started_at: Optional[datetime] = None,
    processed_at: Optional[datetime] = None,
) -> None:
    """
    Update comment processing status.
    
    Args:
        db: Database session
        comment_id: Comment ID
        status: New status (string value)
        error_message: Error message if failed
        processing_started_at: When processing started
        processed_at: When processing completed
    """
    try:
        status_enum = CS(status.lower())
    except ValueError:
        status_enum = CS.PENDING
    
    await db.execute(
        update(Comment)
        .where(Comment.id == comment_id)
        .values(
            status=status_enum,
            error_message=error_message,
            processing_started_at=processing_started_at,
            processed_at=processed_at,
            updated_at=datetime.utcnow(),
        )
    )
    await db.commit()
    
    logger.debug(f"Comment status updated: {comment_id} -> {status}")


async def get_comments_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter_condition: Any = None,
) -> PageResponse[CommentListResponse]:
    """
    Get paginated list of comments.
    
    Args:
        db: Database session
        page: Page number (1-based)
        page_size: Items per page
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        filter_condition: Additional filter conditions
        
    Returns:
        Paginated comment list
    """
    from ..db.models import Comment as DBComment
    query = select(DBComment).options(
        joinedload(DBComment.external_account),
        joinedload(DBComment.user),
    )
    
    if filter_condition:
        query = query.where(filter_condition)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    if sort_by and hasattr(DBComment, sort_by):
        column = getattr(DBComment, sort_by)
        if sort_order == "asc":
            query = query.order_by(asc(column))
        else:
            query = query.order_by(desc(column))
    else:
        query = query.order_by(desc(DBComment.created_at))
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    comments = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1
    
    return PageResponse[CommentListResponse](
        items=[
            CommentListResponse(
                id=c.id,
                text=c.text,
                original_author=c.author_name or c.original_author,
                source_url=c.source_url,
                source_platform=c.source_platform,
                status=c.status.value,
                priority=c.priority.value,
                processed_at=c.processed_at,
                created_at=c.created_at,
            )
            for c in comments
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


async def get_comments_by_status(
    db: AsyncSession,
    status: str,
    limit: int = 100,
) -> List[Comment]:
    """Get comments by status."""
    try:
        status_enum = CS(status.lower())
    except ValueError:
        status_enum = CS.PENDING
    
    result = await db.execute(
        select(Comment)
        .where(Comment.status == status_enum)
        .order_by(desc(Comment.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def get_comments_waiting_processing(
    db: AsyncSession,
    limit: int = 100,
) -> List[Comment]:
    """Get comments that are waiting or processing."""
    result = await db.execute(
        select(Comment)
        .where(
            or_(
                Comment.status == CS.PENDING,
                Comment.status == CS.WAITING,
                Comment.status == CS.PROCESSING,
            )
        )
        .order_by(asc(Comment.priority), asc(Comment.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def count_comments_by_status(
    db: AsyncSession,
) -> Dict[str, int]:
    """Count comments by status."""
    from sqlalchemy import func
    statuses = [s.value for s in CS]
    counts = {}
    
    for status_value in statuses:
        result = await db.execute(
            select(func.count())
            .where(Comment.status == status_value)
        )
        counts[status_value] = result.scalar()
    
    return counts

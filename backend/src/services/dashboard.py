"""
Dashboard service
Provides statistics and insights for the dashboard
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Comment, CommentStatus, Classification, CategoryType, SeverityLevel, BackendType
from ..schemas import (
    DashboardStatsResponse,
    DashboardSummaryResponse,
    CategoryDistributionResponse,
    StatusDistributionResponse,
)

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)


def get_date_range_filter(date_range: str = None) -> Any:
    """
    Get SQLAlchemy filter for date range.
    
    Args:
        date_range: Date range string (1m, 6m, 1y, all)
        
    Returns:
        SQLAlchemy filter condition
    """
    if not date_range or date_range == "all":
        return None
    
    now = datetime.utcnow()
    
    if date_range == "1m":
        start_date = now - timedelta(days=30)
    elif date_range == "6m":
        start_date = now - timedelta(days=180)
    elif date_range == "1y":
        start_date = now - timedelta(days=365)
    else:
        return None
    
    return Comment.created_at >= start_date


async def get_status_counts(
    db: AsyncSession,
    date_range: str = None,
) -> Dict[str, int]:
    """
    Get counts of comments by status.
    
    Args:
        db: Database session
        date_range: Date range filter (1m, 6m, 1y, all)
        
    Returns:
        Dictionary with status counts
    """
    date_filter = get_date_range_filter(date_range)
    
    counts = {}
    for status in CommentStatus:
        filter_cond = and_(
            Comment.status == status,
            date_filter if date_filter else True,
        )
        result = await db.execute(
            select(func.count())
            .where(filter_cond)
        )
        counts[status.value] = result.scalar()
    
    return counts


async def get_category_distribution(
    db: AsyncSession,
    date_range: str = None,
) -> List[CategoryDistributionResponse]:
    """
    Get distribution of classifications by category.
    
    Args:
        db: Database session
        date_range: Date range filter
        
    Returns:
        List of category distribution items
    """
    from sqlalchemy import case
    
    date_filter = get_date_range_filter(date_range)
    
    # Build filter for classifications with date range
    classification_filter = and_(
        Classification.category.isnot(None),
        date_filter if date_filter else True,
    ) if date_filter else Classification.category.isnot(None)
    
    # Get total count
    total_result = await db.execute(
        select(func.count())
        .where(classification_filter)
    )
    total = total_result.scalar()
    
    if total == 0:
        return []
    
    distribution = []
    
    for category in CategoryType:
        count_result = await db.execute(
            select(func.count())
            .where(
                and_(
                    Classification.category == category,
                    classification_filter,
                )
            )
        )
        count = count_result.scalar()
        
        if count > 0:
            percentage = round((count / total * 100), 2)
            
            # Get label
            category_labels = {
                CategoryType.NONE: "No harmful content",
                CategoryType.INCITEMENT_TO_CRIME: "Incitement to crime",
                CategoryType.APPROVAL_OF_ARBITRARY_ACTION: "Approval of arbitrary action",
                CategoryType.INCITEMENT_TO_HATRED: "Incitement to hatred",
                CategoryType.INSULT: "Insult",
                CategoryType.THREAT: "Threat",
                CategoryType.GLORIFICATION_OF_NAZISM: "Glorification of Nazism",
                CategoryType.RELIGIOUS_DEFAMATION: "Religious defamation",
                CategoryType.OTHER: "Other",
            }
            label = category_labels.get(category, category.value)
            
            distribution.append(
                CategoryDistributionResponse(
                    category=category.value,
                    category_label=label,
                    count=count,
                    percentage=percentage,
                )
            )
    
    # Sort by count descending
    distribution.sort(key=lambda x: x.count, reverse=True)
    
    return distribution


async def get_status_distribution(
    db: AsyncSession,
    date_range: str = None,
) -> List[StatusDistributionResponse]:
    """
    Get distribution of comments by status.
    
    Args:
        db: Database session
        date_range: Date range filter
        
    Returns:
        List of status distribution items
    """
    status_counts = await get_status_counts(db, date_range)
    total = sum(status_counts.values())
    
    if total == 0:
        return []
    
    distribution = []
    
    for status, count in status_counts.items():
        if count > 0:
            percentage = round((count / total * 100), 2)
            distribution.append(
                StatusDistributionResponse(
                    status=status,
                    count=count,
                    percentage=percentage,
                )
            )
    
    # Sort by count descending
    distribution.sort(key=lambda x: x.count, reverse=True)
    
    return distribution


async def get_backend_distribution(
    db: AsyncSession,
    date_range: str = None,
) -> Dict[str, int]:
    """
    Get distribution of classifications by backend.
    
    Args:
        db: Database session
        date_range: Date range filter
        
    Returns:
        Dictionary with backend counts
    """
    date_filter = get_date_range_filter(date_range)
    
    distribution = {}
    
    for backend in BackendType:
        filter_cond = and_(
            Classification.backend == backend,
            date_filter if date_filter else True,
        )
        result = await db.execute(
            select(func.count())
            .where(filter_cond)
        )
        distribution[backend.value] = result.scalar()
    
    return distribution


async def get_dashboard_stats(
    db: AsyncSession,
    date_range: str = None,
) -> DashboardStatsResponse:
    """
    Get complete dashboard statistics.
    
    Args:
        db: Database session
        date_range: Date range filter (1m, 6m, 1y, all)
        
    Returns:
        Dashboard statistics response
    """
    # Get status counts
    status_counts = await get_status_counts(db, date_range)
    
    # Get total comments
    date_filter = get_date_range_filter(date_range)
    total_comments_result = await db.execute(
        select(func.count())
        .where(date_filter if date_filter else True)
    )
    total_comments = total_comments_result.scalar()
    
    # Get total classifications
    total_classifications_result = await db.execute(
        select(func.count())
    )
    total_classifications = total_classifications_result.scalar()
    
    # Get flagged counts
    flagged_result = await db.execute(
        select(func.count())
        .where(
            and_(
                Classification.flagged == True,
                date_filter if date_filter else True,
            )
        )
    )
    total_flagged = flagged_result.scalar()
    
    total_not_flagged = total_comments - total_flagged
    flagged_percentage = round((total_flagged / total_comments * 100) if total_comments > 0 else 0, 2)
    
    # Get average harmful
    avg_harmful_result = await db.execute(
        select(func.avg(Classification.harmful))
        .where(date_filter if date_filter else True)
    )
    avg_harmful = float(avg_harmful_result.scalar() or 0)
    
    # Get status distribution
    status_distribution = await get_status_distribution(db, date_range)
    
    # Get category distribution
    category_distribution = await get_category_distribution(db, date_range)
    
    # Get backend distribution
    backend_distribution = await get_backend_distribution(db, date_range)
    
    # Build summary
    summary = DashboardSummaryResponse(
        total_comments=total_comments,
        total_classifications=total_classifications,
        total_flagged=total_flagged,
        total_not_flagged=total_not_flagged,
        flagged_percentage=flagged_percentage,
        average_harmful=round(avg_harmful, 4),
        in_processing=status_counts.get("processing", 0),
        waiting=status_counts.get("waiting", 0),
        processed=status_counts.get("completed", 0),
        pending=status_counts.get("pending", 0),
        failed=status_counts.get("failed", 0),
    )
    
    return DashboardStatsResponse(
        summary=summary,
        status_distribution=status_distribution,
        category_distribution=category_distribution,
        backend_distribution=backend_distribution,
        date_range=date_range or settings.dashboard_default_range,
    )

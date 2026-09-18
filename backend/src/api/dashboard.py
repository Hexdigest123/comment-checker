"""
Dashboard API router
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.session import get_async_db
from ..models import User
from ..schemas import (
    DashboardStatsResponse,
    DashboardSummaryResponse,
    CategoryDistributionResponse,
    StatusDistributionResponse,
)
from ..services.dashboard import get_dashboard_stats
from ..api.auth import get_current_user, get_current_active_user, get_current_admin_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    date_range: str = Query(
        default=settings.dashboard_default_range,
        description="Date range filter (1m, 6m, 1y, all)",
    ),
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DashboardStatsResponse:
    """
    Get dashboard statistics.
    
    Returns comprehensive statistics including:
    - Summary counts (total comments, classifications, flagged, etc.)
    - Status distribution (pending, processing, completed, failed)
    - Category distribution (pie chart data)
    - Backend distribution
    
    Args:
        date_range: Date range filter (1m, 6m, 1y, all)
    """
    # Validate date range
    valid_ranges = ["1m", "6m", "1y", "all"]
    if date_range not in valid_ranges:
        date_range = settings.dashboard_default_range
    
    stats = await get_dashboard_stats(db, date_range)
    
    logger.debug(f"Dashboard stats retrieved for date range: {date_range}")
    
    return stats


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    date_range: str = Query(
        default=settings.dashboard_default_range,
        description="Date range filter (1m, 6m, 1y, all)",
    ),
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DashboardSummaryResponse:
    """
    Get dashboard summary statistics.
    
    Returns just the summary without detailed distributions.
    
    Args:
        date_range: Date range filter (1m, 6m, 1y, all)
    """
    # Validate date range
    valid_ranges = ["1m", "6m", "1y", "all"]
    if date_range not in valid_ranges:
        date_range = settings.dashboard_default_range
    
    stats = await get_dashboard_stats(db, date_range)
    
    return stats.summary


@router.get("/status-distribution", response_model=list[StatusDistributionResponse])
async def get_status_distribution_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    date_range: str = Query(
        default=settings.dashboard_default_range,
        description="Date range filter (1m, 6m, 1y, all)",
    ),
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[StatusDistributionResponse]:
    """
    Get status distribution for the dashboard.
    
    Returns list of status distribution items with counts and percentages.
    
    Args:
        date_range: Date range filter (1m, 6m, 1y, all)
    """
    from ..services.dashboard import get_status_distribution
    
    # Validate date range
    valid_ranges = ["1m", "6m", "1y", "all"]
    if date_range not in valid_ranges:
        date_range = settings.dashboard_default_range
    
    distribution = await get_status_distribution(db, date_range)
    
    return distribution


@router.get("/category-distribution", response_model=list[CategoryDistributionResponse])
async def get_category_distribution_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    date_range: str = Query(
        default=settings.dashboard_default_range,
        description="Date range filter (1m, 6m, 1y, all)",
    ),
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[CategoryDistributionResponse]:
    """
    Get category distribution for the dashboard pie chart.
    
    Returns list of category distribution items with counts and percentages.
    
    Args:
        date_range: Date range filter (1m, 6m, 1y, all)
    """
    from ..services.dashboard import get_category_distribution
    
    # Validate date range
    valid_ranges = ["1m", "6m", "1y", "all"]
    if date_range not in valid_ranges:
        date_range = settings.dashboard_default_range
    
    distribution = await get_category_distribution(db, date_range)
    
    return distribution

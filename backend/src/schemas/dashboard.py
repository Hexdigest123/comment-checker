"""
Dashboard schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StatusDistributionResponse(BaseModel):
    """Status distribution for dashboard."""
    status: str
    count: int
    percentage: float
    
    class Config:
        from_attributes = True


class CategoryDistributionResponse(BaseModel):
    """Category distribution for dashboard."""
    category: str
    category_label: str
    count: int
    percentage: float
    
    class Config:
        from_attributes = True


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary statistics."""
    total_comments: int
    total_classifications: int
    total_flagged: int
    total_not_flagged: int
    flagged_percentage: float
    average_harmful: float
    
    # Status counts
    in_processing: int
    waiting: int
    processed: int
    pending: int
    failed: int
    
    class Config:
        from_attributes = True


class DashboardStatsResponse(BaseModel):
    """Complete dashboard statistics."""
    summary: DashboardSummaryResponse
    status_distribution: List[StatusDistributionResponse]
    category_distribution: List[CategoryDistributionResponse]
    backend_distribution: Dict[str, int]
    date_range: str
    
    class Config:
        from_attributes = True

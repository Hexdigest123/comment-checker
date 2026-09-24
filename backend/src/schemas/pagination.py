"""
Pagination schemas
"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """
    Pagination parameters for list endpoints.
    """
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=10, ge=1, le=100, description="Items per page")
    
    # Sorting
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", description="Sort order: asc or desc")
    
    # Filtering
    search: Optional[str] = Field(default=None, description="Search term")
    
    # Status filter for comments
    status: Optional[str] = Field(default=None, description="Filter by status")
    
    # Date range filter
    start_date: Optional[str] = Field(default=None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(default=None, description="End date (ISO format)")
    
    # Category filter
    category: Optional[str] = Field(default=None, description="Filter by category")

    # Severity filter
    severity: Optional[str] = Field(default=None, description="Filter by severity")

    # Backend filter
    backend: Optional[str] = Field(default=None, description="Filter by backend")
    
    # Flagged filter
    flagged: Optional[bool] = Field(default=None, description="Filter by flagged status")


class PageResponse(BaseModel, Generic[T]):
    """
    Paginated response wrapper.
    """
    items: List[T]
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_previous: bool = Field(description="Whether there is a previous page")

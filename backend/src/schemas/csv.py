"""
CSV upload schemas
"""

from pydantic import BaseModel, Field


class CSVUploadResponse(BaseModel):
    """Response after CSV upload."""
    message: str = Field(..., description="Upload status message")
    batch_id: str = Field(..., description="Unique batch ID for tracking")
    total_rows: int = Field(..., description="Total rows in CSV")
    valid_rows: int = Field(..., description="Valid rows processed")
    invalid_rows: int = Field(default=0, description="Invalid rows skipped")
    processing: bool = Field(default=True, description="Whether processing is async")
    
    class Config:
        from_attributes = True

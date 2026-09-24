"""
Import API router: ingest comments from external sources.

Currently supports ExportComments.com, which exports comments from 20+
social media platforms (Instagram, YouTube, Facebook, TikTok, Twitter/X, ...)
given a post/video URL.
"""

import asyncio
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db.models import User
from ..api.auth import get_current_active_user
from ..services.exportcomments import (
    ExportCommentsClient,
    ExportCommentsError,
    import_from_url,
)

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Import"])


class ImportRequest(BaseModel):
    """Request to import comments from a social media URL."""
    url: str = Field(..., min_length=1, description="Social media post/video URL")
    context: Optional[str] = Field(
        default=None,
        description="Context the comments react to (used for classification)",
    )
    include_replies: bool = Field(default=False, description="Include reply threads")
    max_comments: Optional[int] = Field(
        default=None, ge=1, le=20000, description="Limit number of comments imported"
    )
    timeout: int = Field(
        default=300, ge=30, le=1800, description="Seconds to wait for the export job"
    )


class ImportResponse(BaseModel):
    """Response for a started import."""
    status: str
    url: str
    message: str


@router.get("/exportcomments/status", response_model=dict)
async def exportcomments_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Report whether the ExportComments integration is configured."""
    return {
        "configured": bool(settings.exportcomments_api_key),
        "platforms": [
            "instagram", "youtube", "facebook", "tiktok", "twitter",
            "reddit", "linkedin", "tiktok", "vimeo", "pinterest",
        ],
    }


@router.post("/exportcomments", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_from_exportcomments(
    request: ImportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ImportResponse:
    """
    Start importing comments for a social media URL via ExportComments.com.

    The export job runs in the background. Imported comments appear in the
    comments table with status PENDING and are classified by the worker.
    """
    if not settings.exportcomments_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "ExportComments is not configured. Set EXPORTCOMMENTS_API_KEY "
                "in the backend environment (requires ExportComments "
                "Premium/Business plan)."
            ),
        )

    # Validate the API key works before accepting the job
    try:
        client = ExportCommentsClient()
        await client.close()
    except ExportCommentsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    async def _run() -> None:
        try:
            await import_from_url(
                url=request.url,
                user_id=current_user.id,
                context=request.context,
                include_replies=request.include_replies,
                timeout=request.timeout,
                max_comments=request.max_comments,
            )
        except ExportCommentsError as e:
            logger.error("ExportComments import failed: %s", e)
        except Exception as e:
            logger.error("Unexpected import error: %s", e, exc_info=True)

    asyncio.create_task(_run())

    return ImportResponse(
        status="started",
        url=request.url,
        message=(
            "Export started. Comments will appear in the Comments table "
            "as they are imported and will be classified automatically."
        ),
    )

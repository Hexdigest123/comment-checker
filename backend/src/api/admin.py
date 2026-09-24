"""
Admin API router
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import get_current_admin_user
from ..db.models import (
    AccountCluster,
    Classification,
    ClusterConnection,
    Comment,
    CommentMention,
    CommentStatus,
    ExternalAccount,
    User,
)
from ..db.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])


class DeleteAllCommentsResponse(BaseModel):
    message: str
    deleted_comments: int


class WipeGraphResponse(BaseModel):
    message: str
    deleted_clusters: int
    deleted_accounts: int
    deleted_connections: int


class ReclassifyAllCommentsResponse(BaseModel):
    message: str
    queued_comments: int


@router.delete(
    "/comments",
    response_model=DeleteAllCommentsResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_all_comments(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> DeleteAllCommentsResponse:
    """
    Delete every comment (and its classifications). Admin only.
    """
    await db.execute(delete(Classification))
    comments_result = await db.execute(delete(Comment))
    await db.commit()

    deleted = comments_result.rowcount

    logger.info(f"All comments deleted by admin user {current_user.id}: {deleted} comments")

    return DeleteAllCommentsResponse(
        message="All comments deleted",
        deleted_comments=deleted,
    )


@router.delete(
    "/graph",
    response_model=WipeGraphResponse,
    status_code=status.HTTP_200_OK,
)
async def wipe_graph(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> WipeGraphResponse:
    """
    Delete every cluster, external account, and cluster connection. Admin only.

    Comments are kept but detached from their authors; mentions that point
    at deleted accounts are removed.
    """
    await db.execute(delete(CommentMention))
    await db.execute(update(Comment).values(external_account_id=None))
    connections_result = await db.execute(delete(ClusterConnection))
    accounts_result = await db.execute(delete(ExternalAccount))
    clusters_result = await db.execute(delete(AccountCluster))
    await db.commit()

    logger.info(
        f"Graph wiped by admin user {current_user.id}: "
        f"{clusters_result.rowcount} clusters, {accounts_result.rowcount} accounts, "
        f"{connections_result.rowcount} connections"
    )

    return WipeGraphResponse(
        message="Graph wiped",
        deleted_clusters=clusters_result.rowcount,
        deleted_accounts=accounts_result.rowcount,
        deleted_connections=connections_result.rowcount,
    )


@router.post(
    "/comments/reclassify",
    response_model=ReclassifyAllCommentsResponse,
    status_code=status.HTTP_200_OK,
)
async def reclassify_all_comments(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> ReclassifyAllCommentsResponse:
    """
    Queue every comment for re-classification. Admin only.

    Existing classifications are removed and comments are reset to PENDING
    so the classification worker re-drains them.
    """
    await db.execute(delete(Classification))
    comments_result = await db.execute(
        update(Comment)
        .values(
            status=CommentStatus.PENDING,
            processing_started_at=None,
            processed_at=None,
            error_message=None,
        )
    )
    await db.commit()

    queued = comments_result.rowcount

    logger.info(f"All comments queued for reclassification by admin user {current_user.id}: {queued} comments")

    return ReclassifyAllCommentsResponse(
        message="All comments queued for reclassification",
        queued_comments=queued,
    )

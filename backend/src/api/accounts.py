"""
External Accounts API router
"""

import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_, desc, asc

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import ExternalAccount, AccountCluster, PlatformEnum
from ..db.models.external_account import PlatformEnum as PE
from ..schemas import (
    ExternalAccountCreate,
    ExternalAccountUpdate,
    ExternalAccountResponse,
    ExternalAccountListResponse,
    PageParams,
    PageResponse,
)
from ..services.clustering import ClusteringService
from ..api.auth import get_current_user, get_current_active_user, get_current_admin_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/external-accounts", tags=["External Accounts"])


@router.get("/", response_model=PageResponse[ExternalAccountListResponse])
async def list_external_accounts(
    params: PageParams = Depends(),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    platform: Optional[str] = Query(None, description="Filter by platform"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    search: Optional[str] = Query(None, description="Search in username, display name, bio"),
) -> PageResponse[ExternalAccountListResponse]:
    """
    List external accounts with pagination, search, sort, and filter.
    
    Supports:
    - Pagination (page, page_size)
    - Search (search term in username, display_name, bio)
    - Sort (sort_by, sort_order)
    - Filter by platform, cluster_id
    """
    from sqlalchemy import select, func
    
    # Build filter conditions
    filter_conditions = []
    
    # Platform filter
    if platform:
        try:
            platform_enum = PE(platform.lower())
            filter_conditions.append(ExternalAccount.platform == platform_enum)
        except ValueError:
            pass
    
    # Cluster filter
    if cluster_id:
        filter_conditions.append(ExternalAccount.cluster_id == cluster_id)
    
    # Search filter
    if search:
        search_pattern = f"%{search}%"
        search_conditions = [
            ExternalAccount.username.ilike(search_pattern),
            ExternalAccount.display_name.ilike(search_pattern),
            ExternalAccount.bio.ilike(search_pattern),
        ]
        filter_conditions.append(or_(*search_conditions))
    
    # Combine all conditions
    combined_filter = and_(*filter_conditions) if filter_conditions else None
    
    # Build query
    query = select(ExternalAccount)
    if combined_filter:
        query = query.where(combined_filter)
    
    # Sort
    sort_by = params.sort_by or "created_at"
    sort_order = params.sort_order or "desc"
    
    if sort_by == "username":
        if sort_order == "asc":
            query = query.order_by(asc(ExternalAccount.username))
        else:
            query = query.order_by(desc(ExternalAccount.username))
    elif sort_by == "platform":
        if sort_order == "asc":
            query = query.order_by(asc(ExternalAccount.platform))
        else:
            query = query.order_by(desc(ExternalAccount.platform))
    elif sort_by == "follower_count":
        if sort_order == "asc":
            query = query.order_by(asc(ExternalAccount.follower_count))
        else:
            query = query.order_by(desc(ExternalAccount.follower_count))
    else:
        if sort_order == "asc":
            query = query.order_by(asc(ExternalAccount.created_at))
        else:
            query = query.order_by(desc(ExternalAccount.created_at))
    
    # Count total
    count_query = select(func.count()).select_from(ExternalAccount)
    if combined_filter:
        count_query = count_query.where(combined_filter)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    query = query.limit(params.page_size).offset((params.page - 1) * params.page_size)
    result = await db.execute(query)
    accounts = result.scalars().all()
    
    # Build response
    items = []
    for account in accounts:
        items.append(ExternalAccountListResponse(
            id=account.id,
            platform=account.platform.value,
            platform_user_id=account.platform_user_id,
            username=account.username,
            display_name=account.display_name,
            profile_url=account.profile_url,
            avatar_url=account.avatar_url,
            bio=account.bio,
            follower_count=account.follower_count,
            following_count=account.following_count,
            post_count=account.post_count,
            verified=account.verified,
            cluster_id=account.cluster_id,
            is_active=account.is_active,
            last_seen_at=account.last_seen_at,
            created_at=account.created_at,
            updated_at=account.updated_at,
        ))
    
    return PageResponse[ExternalAccountListResponse](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=(total + params.page_size - 1) // params.page_size if total > 0 else 0
    )


@router.get("/{account_id}", response_model=ExternalAccountResponse)
async def get_external_account(
    account_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ExternalAccountResponse:
    """Get a single external account by ID."""
    result = await db.execute(
        select(ExternalAccount).where(ExternalAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External account not found",
        )
    
    return ExternalAccountResponse(
        id=account.id,
        platform=account.platform.value,
        platform_user_id=account.platform_user_id,
        username=account.username,
        display_name=account.display_name,
        profile_url=account.profile_url,
        avatar_url=account.avatar_url,
        bio=account.bio,
        follower_count=account.follower_count,
        following_count=account.following_count,
        post_count=account.post_count,
        verified=account.verified,
        cluster_id=account.cluster_id,
        is_active=account.is_active,
        last_seen_at=account.last_seen_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        comments=[
            {
                "id": c.id,
                "text": c.text[:200] + "..." if len(c.text) > 200 else c.text,
                "status": c.status.value,
                "created_at": c.created_at
            }
            for c in account.comments
        ] if account.comments else [],
        cluster={
            "id": account.cluster.id,
            "name": account.cluster.name,
            "type": account.cluster.cluster_type.value,
            "toxicity_score": account.cluster.toxicity_score,
            "comment_count": account.cluster.comment_count
        } if account.cluster else None
    )


@router.post("/", response_model=ExternalAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_external_account(
    account_create: ExternalAccountCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ExternalAccountResponse:
    """Create a new external account."""
    # Validate platform
    try:
        platform = PE(account_create.platform.lower())
    except ValueError:
        platform = PE.OTHER
    
    # Check if account already exists
    result = await db.execute(
        select(ExternalAccount).where(
            ExternalAccount.platform == platform,
            ExternalAccount.username == account_create.username
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account with this platform and username already exists",
        )
    
    # Create new account
    account = ExternalAccount(
        id=str(uuid.uuid4()),
        platform=platform,
        platform_user_id=account_create.platform_user_id,
        username=account_create.username,
        display_name=account_create.display_name,
        profile_url=account_create.profile_url,
        avatar_url=account_create.avatar_url,
        bio=account_create.bio,
        follower_count=account_create.follower_count,
        following_count=account_create.following_count,
        post_count=account_create.post_count,
        verified=account_create.verified or False,
        is_active=True,
    )
    
    db.add(account)
    await db.commit()
    await db.refresh(account)
    
    # Auto-cluster by username/platform
    clustering_service = ClusteringService(db)
    await clustering_service.auto_cluster_by_username(
        platform=platform.value,
        username=account.username or "",
        user_id=current_user.id
    )
    
    await db.refresh(account)
    
    logger.info(f"External account created: {account.id}")
    
    return ExternalAccountResponse(
        id=account.id,
        platform=account.platform.value,
        platform_user_id=account.platform_user_id,
        username=account.username,
        display_name=account.display_name,
        profile_url=account.profile_url,
        avatar_url=account.avatar_url,
        bio=account.bio,
        follower_count=account.follower_count,
        following_count=account.following_count,
        post_count=account.post_count,
        verified=account.verified,
        cluster_id=account.cluster_id,
        is_active=account.is_active,
        last_seen_at=account.last_seen_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        comments=[],
        cluster=None
    )


@router.put("/{account_id}", response_model=ExternalAccountResponse)
async def update_external_account(
    account_id: str,
    account_update: ExternalAccountUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ExternalAccountResponse:
    """Update an external account."""
    result = await db.execute(
        select(ExternalAccount).where(ExternalAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External account not found",
        )
    
    # Update fields
    if account_update.platform:
        try:
            account.platform = PE(account_update.platform.lower())
        except ValueError:
            account.platform = PE.OTHER
    
    if account_update.username:
        account.username = account_update.username
    if account_update.display_name:
        account.display_name = account_update.display_name
    if account_update.profile_url:
        account.profile_url = account_update.profile_url
    if account_update.avatar_url:
        account.avatar_url = account_update.avatar_url
    if account_update.bio:
        account.bio = account_update.bio
    if account_update.follower_count is not None:
        account.follower_count = account_update.follower_count
    if account_update.following_count is not None:
        account.following_count = account_update.following_count
    if account_update.post_count is not None:
        account.post_count = account_update.post_count
    if account_update.verified is not None:
        account.verified = account_update.verified
    if account_update.is_active is not None:
        account.is_active = account_update.is_active
    
    account.updated_at = func.now()
    
    db.add(account)
    await db.commit()
    await db.refresh(account)
    
    logger.info(f"External account updated: {account.id}")
    
    return ExternalAccountResponse(
        id=account.id,
        platform=account.platform.value,
        platform_user_id=account.platform_user_id,
        username=account.username,
        display_name=account.display_name,
        profile_url=account.profile_url,
        avatar_url=account.avatar_url,
        bio=account.bio,
        follower_count=account.follower_count,
        following_count=account.following_count,
        post_count=account.post_count,
        verified=account.verified,
        cluster_id=account.cluster_id,
        is_active=account.is_active,
        last_seen_at=account.last_seen_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        comments=[
            {
                "id": c.id,
                "text": c.text[:200] + "..." if len(c.text) > 200 else c.text,
                "status": c.status.value,
                "created_at": c.created_at
            }
            for c in account.comments
        ] if account.comments else [],
        cluster={
            "id": account.cluster.id,
            "name": account.cluster.name,
            "type": account.cluster.cluster_type.value
        } if account.cluster else None
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_external_account(
    account_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """Delete an external account. Admin only."""
    result = await db.execute(
        select(ExternalAccount).where(ExternalAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External account not found",
        )
    
    # Remove from cluster (don't delete cluster)
    account.cluster_id = None
    await db.commit()
    
    # Delete account
    await db.delete(account)
    await db.commit()
    
    logger.info(f"External account deleted: {account_id}")


@router.post("/{account_id}/assign-cluster/{cluster_id}", response_model=ExternalAccountResponse)
async def assign_account_to_cluster(
    account_id: str,
    cluster_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ExternalAccountResponse:
    """Assign an external account to a cluster."""
    result = await db.execute(
        select(ExternalAccount).where(ExternalAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External account not found",
        )
    
    # Check if cluster exists
    result = await db.execute(
        select(AccountCluster).where(AccountCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )
    
    # Assign account to cluster
    account.cluster_id = cluster_id
    db.add(account)
    await db.commit()
    await db.refresh(account)
    
    # Update cluster metadata
    clustering_service = ClusteringService(db)
    await clustering_service._update_cluster_metadata(cluster_id)
    
    logger.info(f"Account {account_id} assigned to cluster {cluster_id}")
    
    return ExternalAccountResponse(
        id=account.id,
        platform=account.platform.value,
        platform_user_id=account.platform_user_id,
        username=account.username,
        display_name=account.display_name,
        profile_url=account.profile_url,
        avatar_url=account.avatar_url,
        bio=account.bio,
        follower_count=account.follower_count,
        following_count=account.following_count,
        post_count=account.post_count,
        verified=account.verified,
        cluster_id=account.cluster_id,
        is_active=account.is_active,
        last_seen_at=account.last_seen_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        comments=[],
        cluster={
            "id": cluster.id,
            "name": cluster.name,
            "type": cluster.cluster_type.value
        }
    )


@router.post("/{account_id}/remove-from-cluster", response_model=ExternalAccountResponse)
async def remove_account_from_cluster(
    account_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ExternalAccountResponse:
    """Remove an external account from its cluster."""
    result = await db.execute(
        select(ExternalAccount).where(ExternalAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External account not found",
        )
    
    if account.cluster_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not in any cluster",
        )
    
    cluster_id = account.cluster_id
    account.cluster_id = None
    db.add(account)
    await db.commit()
    
    # Update cluster metadata
    clustering_service = ClusteringService(db)
    await clustering_service._update_cluster_metadata(cluster_id)
    
    await db.refresh(account)
    
    logger.info(f"Account {account_id} removed from cluster {cluster_id}")
    
    return ExternalAccountResponse(
        id=account.id,
        platform=account.platform.value,
        platform_user_id=account.platform_user_id,
        username=account.username,
        display_name=account.display_name,
        profile_url=account.profile_url,
        avatar_url=account.avatar_url,
        bio=account.bio,
        follower_count=account.follower_count,
        following_count=account.following_count,
        post_count=account.post_count,
        verified=account.verified,
        cluster_id=account.cluster_id,
        is_active=account.is_active,
        last_seen_at=account.last_seen_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        comments=[],
        cluster=None
    )

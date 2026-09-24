"""
Account Clusters API router
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_, desc, asc, select, func
from sqlalchemy.orm import joinedload, selectinload

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import AccountCluster, ClusterConnection, User
from ..db.models.account_cluster import ClusterTypeEnum, DiscoveryMethodEnum
from ..db.models.cluster_connection import ConnectionTypeEnum, ConnectionStatusEnum
from ..schemas import (
    ClusterCreate,
    ClusterUpdate,
    ClusterResponse,
    ClusterListResponse,
    ClusterGraphResponse,
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionListResponse,
    PageParams,
    PageResponse,
)
from ..services.clustering import ClusteringService
from ..api.auth import get_current_active_user, get_current_admin_user

settings = get_settings()

logger = logging.getLogger(__name__)


def _ev(v):
    """Return the string value of an enum member or the value itself."""
    return v.value if hasattr(v, "value") else v

router = APIRouter(tags=["Clusters"])


@router.get("/graph", response_model=ClusterGraphResponse)
async def get_full_graph(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    include_comments: bool = True,
) -> ClusterGraphResponse:
    """
    Get the full entity graph: clusters, their accounts, and connections.

    Returns nodes and links for force-directed graph visualization.
    When include_comments is true, each comment authored by an account is
    returned as a node linked to that account.
    """
    clustering_service = ClusteringService(db)
    graph_data = await clustering_service.get_cluster_graph(
        None, include_comments=include_comments
    )

    return ClusterGraphResponse(
        nodes=graph_data["nodes"],
        links=graph_data["links"]
    )


@router.get("/", response_model=PageResponse[ClusterListResponse])
async def list_clusters(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    params: PageParams = Depends(),
    cluster_type: Optional[str] = Query(None, description="Filter by cluster type"),
    discovery_method: Optional[str] = Query(None, description="Filter by discovery method"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    min_toxicity: Optional[float] = Query(None, description="Minimum toxicity score (0-1)"),
    max_toxicity: Optional[float] = Query(None, description="Maximum toxicity score (0-1)"),
) -> PageResponse[ClusterListResponse]:
    """
    List account clusters with pagination, search, sort, and filter.
    
    Supports:
    - Pagination (page, page_size)
    - Search (search term in name, description)
    - Sort (sort_by, sort_order)
    - Filter by cluster_type, discovery_method, toxicity_score
    """
    filter_conditions = []
    
    if cluster_type:
        try:
            type_enum = ClusterTypeEnum(cluster_type.lower())
            filter_conditions.append(AccountCluster.cluster_type == type_enum)
        except ValueError:
            pass
    
    # Discovery method filter
    if discovery_method:
        try:
            method_enum = DiscoveryMethodEnum(discovery_method.lower())
            filter_conditions.append(AccountCluster.discovery_method == method_enum)
        except ValueError:
            pass
    
    # Search filter
    if search:
        search_pattern = f"%{search}%"
        search_conditions = [
            AccountCluster.name.ilike(search_pattern),
            AccountCluster.description.ilike(search_pattern),
        ]
        filter_conditions.append(or_(*search_conditions))
    
    # Toxicity score filter
    if min_toxicity is not None:
        filter_conditions.append(AccountCluster.toxicity_score >= min_toxicity)
    if max_toxicity is not None:
        filter_conditions.append(AccountCluster.toxicity_score <= max_toxicity)
    combined_filter = and_(*filter_conditions) if filter_conditions else None
    
    query = select(AccountCluster)
    if combined_filter is not None:
        query = query.where(combined_filter)
    sort_by = params.sort_by or "toxicity_score"
    sort_order = params.sort_order or "desc"
    
    if sort_by == "name":
        if sort_order == "asc":
            query = query.order_by(asc(AccountCluster.name))
        else:
            query = query.order_by(desc(AccountCluster.name))
    elif sort_by == "comment_count":
        if sort_order == "asc":
            query = query.order_by(asc(AccountCluster.comment_count))
        else:
            query = query.order_by(desc(AccountCluster.comment_count))
    elif sort_by == "created_at":
        if sort_order == "asc":
            query = query.order_by(asc(AccountCluster.created_at))
        else:
            query = query.order_by(desc(AccountCluster.created_at))
    else:
        if sort_order == "asc":
            query = query.order_by(asc(AccountCluster.toxicity_score))
        else:
            query = query.order_by(desc(AccountCluster.toxicity_score))
    count_query = select(func.count()).select_from(AccountCluster)
    if combined_filter is not None:
        count_query = count_query.where(combined_filter)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    query = query.limit(params.page_size).offset((params.page - 1) * params.page_size)
    result = await db.execute(
        query.options(
            selectinload(AccountCluster.accounts),
            selectinload(AccountCluster.owner)
        )
    )
    clusters = result.scalars().all()
    
    items = []
    for cluster in clusters:
        items.append(ClusterListResponse(
            id=cluster.id,
            name=cluster.name,
            description=cluster.description,
            cluster_type=_ev(cluster.cluster_type),
            discovery_method=_ev(cluster.discovery_method),
            owner_id=cluster.owner_id,
            owner_name=cluster.owner.full_name if cluster.owner else None,
            color=cluster.color,
            icon=cluster.icon,
            is_verified=cluster.is_verified,
            comment_count=cluster.comment_count,
            toxicity_score=cluster.toxicity_score,
            last_activity_at=cluster.last_activity_at,
            account_count=len(cluster.accounts) if cluster.accounts else 0,
            created_at=cluster.created_at,
            updated_at=cluster.updated_at,
        ))
    
    total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0
    return PageResponse[ClusterListResponse](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_previous=params.page > 1,
    )


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(
    cluster_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClusterResponse:
    """Get a single cluster by ID with all related data."""
    clustering_service = ClusteringService(db)
    cluster = await clustering_service.get_cluster(cluster_id)
    
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )
    
    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        description=cluster.description,
        cluster_type=_ev(cluster.cluster_type),
        discovery_method=_ev(cluster.discovery_method),
        owner_id=cluster.owner_id,
        owner_name=cluster.owner.full_name if cluster.owner else None,
        color=cluster.color,
        icon=cluster.icon,
        is_verified=cluster.is_verified,
        comment_count=cluster.comment_count,
        toxicity_score=cluster.toxicity_score,
        last_activity_at=cluster.last_activity_at,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        accounts=[
            {
                "id": a.id,
                "platform": _ev(a.platform),
                "username": a.username,
                "display_name": a.display_name,
                "profile_url": a.profile_url,
                "follower_count": a.follower_count,
                "verified": a.verified,
                "comment_count": len(a.comments) if a.comments else 0
            }
            for a in cluster.accounts
        ] if cluster.accounts else [],
        connections_out=[
            {
                "id": c.id,
                "cluster_a_id": c.cluster_a_id,
                "cluster_b_id": c.cluster_b_id,
                "cluster_b_name": c.cluster_b.name if c.cluster_b else None,
                "connection_type": _ev(c.connection_type),
                "confidence": c.confidence,
                "status": _ev(c.status),
                "created_at": c.created_at
            }
            for c in cluster.connections_out
        ] if cluster.connections_out else [],
        connections_in=[
            {
                "id": c.id,
                "cluster_a_id": c.cluster_a_id,
                "cluster_a_name": c.cluster_a.name if c.cluster_a else None,
                "cluster_b_id": c.cluster_b_id,
                "connection_type": _ev(c.connection_type),
                "confidence": c.confidence,
                "status": _ev(c.status),
                "created_at": c.created_at
            }
            for c in cluster.connections_in
        ] if cluster.connections_in else [],
        platform_distribution=cluster.platform_distribution,
        total_followers=cluster.total_followers
    )


@router.post("/", response_model=ClusterResponse, status_code=status.HTTP_201_CREATED)
async def create_cluster(
    cluster_create: ClusterCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClusterResponse:
    """Create a new account cluster."""
    clustering_service = ClusteringService(db)
    try:
        cluster_type = ClusterTypeEnum(cluster_create.cluster_type.lower())
    except ValueError:
        cluster_type = ClusterTypeEnum.UNKNOWN
    try:
        discovery_method = DiscoveryMethodEnum(cluster_create.discovery_method.lower())
    except ValueError:
        discovery_method = DiscoveryMethodEnum.MANUAL
    
    cluster = await clustering_service.create_cluster(
        name=cluster_create.name,
        description=cluster_create.description,
        cluster_type=cluster_type,
        owner_id=current_user.id,
        color=cluster_create.color,
        account_ids=cluster_create.account_ids
    )
    
    logger.info(f"Cluster created: {cluster.id}")
    
    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        description=cluster.description,
        cluster_type=_ev(cluster.cluster_type),
        discovery_method=_ev(cluster.discovery_method),
        owner_id=cluster.owner_id,
        owner_name=cluster.owner.full_name if cluster.owner else None,
        color=cluster.color,
        icon=cluster.icon,
        is_verified=cluster.is_verified,
        comment_count=cluster.comment_count,
        toxicity_score=cluster.toxicity_score,
        last_activity_at=cluster.last_activity_at,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        accounts=[
            {
                "id": a.id,
                "platform": _ev(a.platform),
                "username": a.username,
                "display_name": a.display_name,
                "profile_url": a.profile_url,
                "follower_count": a.follower_count,
                "verified": a.verified,
                "comment_count": len(a.comments) if a.comments else 0
            }
            for a in cluster.accounts
        ] if cluster.accounts else [],
        connections_out=[],
        connections_in=[],
        platform_distribution=cluster.platform_distribution,
        total_followers=cluster.total_followers
    )


@router.put("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: str,
    cluster_update: ClusterUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ClusterResponse:
    """Update a cluster."""
    clustering_service = ClusteringService(db)
    cluster = await clustering_service.get_cluster(cluster_id)
    
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )
    update_kwargs = {}
    if cluster_update.name:
        update_kwargs["name"] = cluster_update.name
    if cluster_update.description:
        update_kwargs["description"] = cluster_update.description
    if cluster_update.cluster_type:
        try:
            update_kwargs["cluster_type"] = ClusterTypeEnum(cluster_update.cluster_type.lower())
        except ValueError:
            pass
    if cluster_update.color:
        update_kwargs["color"] = cluster_update.color
    if cluster_update.icon:
        update_kwargs["icon"] = cluster_update.icon
    if cluster_update.is_verified is not None:
        update_kwargs["is_verified"] = cluster_update.is_verified
    
    cluster = await clustering_service.update_cluster(cluster_id, **update_kwargs)
    
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )
    
    await db.refresh(cluster)
    
    logger.info(f"Cluster updated: {cluster.id}")
    
    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        description=cluster.description,
        cluster_type=_ev(cluster.cluster_type),
        discovery_method=_ev(cluster.discovery_method),
        owner_id=cluster.owner_id,
        owner_name=cluster.owner.full_name if cluster.owner else None,
        color=cluster.color,
        icon=cluster.icon,
        is_verified=cluster.is_verified,
        comment_count=cluster.comment_count,
        toxicity_score=cluster.toxicity_score,
        last_activity_at=cluster.last_activity_at,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        accounts=[
            {
                "id": a.id,
                "platform": _ev(a.platform),
                "username": a.username,
                "display_name": a.display_name,
                "profile_url": a.profile_url,
                "follower_count": a.follower_count,
                "verified": a.verified,
                "comment_count": len(a.comments) if a.comments else 0
            }
            for a in cluster.accounts
        ] if cluster.accounts else [],
        connections_out=[
            {
                "id": c.id,
                "cluster_a_id": c.cluster_a_id,
                "cluster_b_id": c.cluster_b_id,
                "cluster_b_name": c.cluster_b.name if c.cluster_b else None,
                "connection_type": _ev(c.connection_type),
                "confidence": c.confidence,
                "status": _ev(c.status),
                "created_at": c.created_at
            }
            for c in cluster.connections_out
        ] if cluster.connections_out else [],
        connections_in=[
            {
                "id": c.id,
                "cluster_a_id": c.cluster_a_id,
                "cluster_a_name": c.cluster_a.name if c.cluster_a else None,
                "cluster_b_id": c.cluster_b_id,
                "connection_type": _ev(c.connection_type),
                "confidence": c.confidence,
                "status": _ev(c.status),
                "created_at": c.created_at
            }
            for c in cluster.connections_in
        ] if cluster.connections_in else [],
        platform_distribution=cluster.platform_distribution,
        total_followers=cluster.total_followers
    )


@router.delete("/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cluster(
    cluster_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """Delete a cluster. Admin only."""
    clustering_service = ClusteringService(db)
    
    success = await clustering_service.delete_cluster(cluster_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )
    
    logger.info(f"Cluster deleted: {cluster_id}")


@router.get("/{cluster_id}/graph", response_model=ClusterGraphResponse)
async def get_cluster_graph(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    cluster_id: Optional[str] = None,
    include_comments: bool = True,
) -> ClusterGraphResponse:
    """
    Get cluster graph data for visualization.
    
    Returns nodes and links for D3.js force-directed graph visualization.
    
    Args:
        cluster_id: Optional cluster ID to focus on (returns connected clusters)
        include_comments: Whether to include comment nodes linked to accounts
    """
    clustering_service = ClusteringService(db)
    graph_data = await clustering_service.get_cluster_graph(
        cluster_id, include_comments=include_comments
    )
    
    return ClusterGraphResponse(
        nodes=graph_data["nodes"],
        links=graph_data["links"]
    )


@router.get("/connections", response_model=PageResponse[ConnectionListResponse])
async def list_connections(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    params: PageParams = Depends(),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    status: Optional[str] = Query(None, description="Filter by connection status"),
    connection_type: Optional[str] = Query(None, description="Filter by connection type"),
) -> PageResponse[ConnectionListResponse]:
    """
    List cluster connections with pagination and filtering.
    
    Supports:
    - Pagination (page, page_size)
    - Filter by cluster_id, status, connection_type
    """
    clustering_service = ClusteringService(db)
    filter_conditions = []
    
    if cluster_id:
        filter_conditions.append(
            or_(
                ClusterConnection.cluster_a_id == cluster_id,
                ClusterConnection.cluster_b_id == cluster_id
            )
        )
    
    if status:
        try:
            status_enum = ConnectionStatusEnum(status.lower())
            filter_conditions.append(ClusterConnection.status == status_enum)
        except ValueError:
            pass
    
    if connection_type:
        try:
            type_enum = ConnectionTypeEnum(connection_type.lower())
            filter_conditions.append(ClusterConnection.connection_type == type_enum)
        except ValueError:
            pass
    combined_filter = and_(*filter_conditions) if filter_conditions else None
    
    connections, total = await clustering_service.get_connections(
        cluster_id=cluster_id,
        status=status_enum if status else None,
        limit=params.page_size,
        offset=(params.page - 1) * params.page_size
    )
    
    items = []
    for conn in connections:
        items.append(ConnectionListResponse(
            id=conn.id,
            cluster_a_id=conn.cluster_a_id,
            cluster_a_name=conn.cluster_a.name if conn.cluster_a else None,
            cluster_b_id=conn.cluster_b_id,
            cluster_b_name=conn.cluster_b.name if conn.cluster_b else None,
            connection_type=_ev(conn.connection_type),
            confidence=conn.confidence,
            status=_ev(conn.status),
            created_by_id=conn.created_by_id,
            created_by_name=conn.created_by.name if conn.created_by else None,
            evidence=conn.evidence,
            notes=conn.notes,
            verified_at=conn.verified_at,
            verified_by_id=conn.verified_by_id,
            created_at=conn.created_at,
            updated_at=conn.updated_at
        ))
    
    return PageResponse[ConnectionListResponse](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=(total + params.page_size - 1) // params.page_size if total > 0 else 0
    )


@router.get("/connections/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ConnectionResponse:
    """Get a single connection by ID."""
    result = await db.execute(
        select(ClusterConnection)
        .where(ClusterConnection.id == connection_id)
        .options(
            joinedload(ClusterConnection.cluster_a),
            joinedload(ClusterConnection.cluster_b),
            joinedload(ClusterConnection.created_by)
        )
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    
    return ConnectionResponse(
        id=connection.id,
        cluster_a_id=connection.cluster_a_id,
        cluster_a_name=connection.cluster_a.name if connection.cluster_a else None,
        cluster_b_id=connection.cluster_b_id,
        cluster_b_name=connection.cluster_b.name if connection.cluster_b else None,
        connection_type=_ev(connection.connection_type),
        confidence=connection.confidence,
        status=_ev(connection.status),
        created_by_id=connection.created_by_id,
        created_by_name=connection.created_by.name if connection.created_by else None,
        evidence=connection.evidence,
        notes=connection.notes,
        verified_at=connection.verified_at,
        verified_by_id=connection.verified_by_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )


@router.post("/connections", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    connection_create: ConnectionCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ConnectionResponse:
    """Create a new connection between two clusters."""
    clustering_service = ClusteringService(db)
    try:
        connection_type = ConnectionTypeEnum(connection_create.connection_type.lower())
    except ValueError:
        connection_type = ConnectionTypeEnum.SAME_PERSON
    
    connection = await clustering_service.create_connection(
        cluster_a_id=connection_create.cluster_a_id,
        cluster_b_id=connection_create.cluster_b_id,
        connection_type=connection_type,
        confidence=connection_create.confidence,
        created_by_id=current_user.id,
        evidence=connection_create.evidence,
        notes=connection_create.notes
    )
    
    logger.info(f"Connection created: {connection.id}")
    
    return ConnectionResponse(
        id=connection.id,
        cluster_a_id=connection.cluster_a_id,
        cluster_a_name=connection.cluster_a.name if connection.cluster_a else None,
        cluster_b_id=connection.cluster_b_id,
        cluster_b_name=connection.cluster_b.name if connection.cluster_b else None,
        connection_type=_ev(connection.connection_type),
        confidence=connection.confidence,
        status=_ev(connection.status),
        created_by_id=connection.created_by_id,
        created_by_name=connection.created_by.name if connection.created_by else None,
        evidence=connection.evidence,
        notes=connection.notes,
        verified_at=connection.verified_at,
        verified_by_id=connection.verified_by_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )


@router.put("/connections/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: str,
    connection_update: ConnectionUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ConnectionResponse:
    """Update a connection."""
    result = await db.execute(
        select(ClusterConnection).where(ClusterConnection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    if connection_update.connection_type:
        try:
            connection.connection_type = ConnectionTypeEnum(connection_update.connection_type.lower())
        except ValueError:
            pass
    if connection_update.confidence is not None:
        connection.confidence = connection_update.confidence
    if connection_update.evidence:
        connection.evidence = connection_update.evidence
    if connection_update.notes:
        connection.notes = connection_update.notes
    
    connection.updated_at = func.now()
    
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    
    logger.info(f"Connection updated: {connection.id}")
    
    return ConnectionResponse(
        id=connection.id,
        cluster_a_id=connection.cluster_a_id,
        cluster_a_name=connection.cluster_a.name if connection.cluster_a else None,
        cluster_b_id=connection.cluster_b_id,
        cluster_b_name=connection.cluster_b.name if connection.cluster_b else None,
        connection_type=_ev(connection.connection_type),
        confidence=connection.confidence,
        status=_ev(connection.status),
        created_by_id=connection.created_by_id,
        created_by_name=connection.created_by.name if connection.created_by else None,
        evidence=connection.evidence,
        notes=connection.notes,
        verified_at=connection.verified_at,
        verified_by_id=connection.verified_by_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )


@router.post("/connections/{connection_id}/confirm", response_model=ConnectionResponse)
async def confirm_connection(
    connection_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ConnectionResponse:
    """Confirm a proposed connection."""
    clustering_service = ClusteringService(db)
    
    success = await clustering_service.confirm_connection(connection_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    result = await db.execute(
        select(ClusterConnection)
        .where(ClusterConnection.id == connection_id)
        .options(
            joinedload(ClusterConnection.cluster_a),
            joinedload(ClusterConnection.cluster_b),
            joinedload(ClusterConnection.created_by)
        )
    )
    connection = result.scalar_one_or_none()
    
    logger.info(f"Connection confirmed: {connection.id}")
    
    return ConnectionResponse(
        id=connection.id,
        cluster_a_id=connection.cluster_a_id,
        cluster_a_name=connection.cluster_a.name if connection.cluster_a else None,
        cluster_b_id=connection.cluster_b_id,
        cluster_b_name=connection.cluster_b.name if connection.cluster_b else None,
        connection_type=_ev(connection.connection_type),
        confidence=connection.confidence,
        status=_ev(connection.status),
        created_by_id=connection.created_by_id,
        created_by_name=connection.created_by.name if connection.created_by else None,
        evidence=connection.evidence,
        notes=connection.notes,
        verified_at=connection.verified_at,
        verified_by_id=connection.verified_by_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> None:
    """Delete a connection. Admin only."""
    result = await db.execute(
        select(ClusterConnection).where(ClusterConnection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    
    await db.delete(connection)
    await db.commit()
    
    logger.info(f"Connection deleted: {connection_id}")

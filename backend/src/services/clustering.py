"""
Clustering service for managing social media account clusters.

This service handles:
- Automatic clustering of accounts by username on same platform
- Manual cluster creation and management
- Cluster connection management
- Toxicity scoring for clusters
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update, delete, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from ..db.models import (
    ExternalAccount,
    AccountCluster,
    ClusterConnection,
    Comment,
    PlatformEnum,
    ClusterTypeEnum,
    DiscoveryMethodEnum,
    ConnectionTypeEnum,
    ConnectionStatusEnum,
)
from ..db.models.external_account import PlatformEnum as PE


class ClusteringService:
    """Service for managing account clusters."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_account(
        self,
        platform: str,
        username: str,
        **kwargs
    ) -> ExternalAccount:
        """
        Get or create an external account by platform and username.
        
        Args:
            platform: Platform name (twitter, facebook, etc.)
            username: Username on that platform
            **kwargs: Additional account data
            
        Returns:
            ExternalAccount instance
        """
        # Try to find existing account
        try:
            platform_enum = PE(platform.lower())
        except ValueError:
            platform_enum = PE.OTHER
        
        result = await self.db.execute(
            select(ExternalAccount).where(
                ExternalAccount.platform == platform_enum,
                ExternalAccount.username == username
            )
        )
        account = result.scalar_one_or_none()
        
        if account:
            return account
        account = ExternalAccount(
            id=str(uuid.uuid4()),
            platform=platform_enum,
            username=username,
            **kwargs
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        
        return account
    
    async def auto_cluster_by_username(
        self,
        platform: str,
        username: str,
        user_id: Optional[str] = None
    ) -> AccountCluster:
        """
        Automatically create or update a cluster for accounts with the same username.
        
        This implements the rule: "comments on the same Platform with the same Name 
        group them automatic"
        
        Args:
            platform: Platform name
            username: Username
            user_id: Optional internal user ID (for ownership)
            
        Returns:
            AccountCluster instance
        """
        try:
            platform_enum = PE(platform.lower())
        except ValueError:
            platform_enum = PE.OTHER
        result = await self.db.execute(
            select(ExternalAccount)
            .options(selectinload(ExternalAccount.cluster))
            .where(
                ExternalAccount.platform == platform_enum,
                ExternalAccount.username == username
            )
        )
        accounts = result.scalars().all()
        
        if not accounts:
            # No accounts found, create cluster anyway for future use
            cluster = AccountCluster(
                id=str(uuid.uuid4()),
                name=username,
                description=f"Auto-created cluster for {username} on {platform}",
                cluster_type=ClusterTypeEnum.PERSON,
                discovery_method=DiscoveryMethodEnum.AUTO_USERNAME,
                owner_id=user_id,
            )
            self.db.add(cluster)
            await self.db.commit()
            await self.db.refresh(cluster)
            return cluster
        existing_cluster = None
        for account in accounts:
            if account.cluster_id:
                existing_cluster = account.cluster
                break
        
        if existing_cluster:
            # Use existing cluster
            cluster = existing_cluster
        else:
            cluster = AccountCluster(
                id=str(uuid.uuid4()),
                name=username,
                description=f"Auto-created cluster for {username} on {platform}",
                cluster_type=ClusterTypeEnum.PERSON,
                discovery_method=DiscoveryMethodEnum.AUTO_USERNAME,
                owner_id=user_id,
            )
            self.db.add(cluster)
            await self.db.commit()
            await self.db.refresh(cluster)
        
        for account in accounts:
            if account.cluster_id != cluster.id:
                account.cluster_id = cluster.id
                self.db.add(account)
        
        await self.db.commit()
        await self.db.refresh(cluster)
        await self._update_cluster_metadata(cluster.id)
        
        return cluster
    
    async def create_cluster(
        self,
        name: str,
        description: Optional[str] = None,
        cluster_type: ClusterTypeEnum = ClusterTypeEnum.UNKNOWN,
        owner_id: Optional[str] = None,
        color: Optional[str] = None,
        account_ids: Optional[List[str]] = None
    ) -> AccountCluster:
        """
        Create a new account cluster manually.
        
        Args:
            name: Cluster name
            description: Optional description
            cluster_type: Type of cluster
            owner_id: Internal user who owns this cluster
            color: Color for visualization
            account_ids: List of account IDs to add to cluster
            
        Returns:
            AccountCluster instance
        """
        cluster = AccountCluster(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            cluster_type=cluster_type,
            discovery_method=DiscoveryMethodEnum.MANUAL,
            owner_id=owner_id,
            color=color or f"#{uuid.uuid4().hex[:6]}",
        )
        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)
        if account_ids:
            result = await self.db.execute(
                select(ExternalAccount).where(ExternalAccount.id.in_(account_ids))
            )
            accounts = result.scalars().all()
            for account in accounts:
                account.cluster_id = cluster.id
                self.db.add(account)
            await self.db.commit()
            await self._update_cluster_metadata(cluster.id)
        
        return cluster
    
    async def get_cluster(self, cluster_id: str) -> Optional[AccountCluster]:
        """Get a cluster by ID with all related data."""
        result = await self.db.execute(
            select(AccountCluster)
            .where(AccountCluster.id == cluster_id)
            .options(
                selectinload(AccountCluster.accounts),
                selectinload(AccountCluster.connections_out),
                selectinload(AccountCluster.connections_in),
                selectinload(AccountCluster.owner)
            )
        )
        return result.scalar_one_or_none()
    
    async def get_clusters(
        self,
        owner_id: Optional[str] = None,
        cluster_type: Optional[ClusterTypeEnum] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[AccountCluster], int]:
        """
        Get a list of clusters with optional filtering.
        
        Args:
            owner_id: Filter by owner
            cluster_type: Filter by type
            search: Search in name and description
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            Tuple of (clusters, total_count)
        """
        query = select(AccountCluster)
        count_query = select(func.count()).select_from(AccountCluster)
        conditions = []
        if owner_id:
            conditions.append(AccountCluster.owner_id == owner_id)
        if cluster_type:
            conditions.append(AccountCluster.cluster_type == cluster_type)
        if search:
            conditions.append(
                or_(
                    AccountCluster.name.ilike(f"%{search}%"),
                    AccountCluster.description.ilike(f"%{search}%")
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        query = query.order_by(AccountCluster.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(
            query.options(
                selectinload(AccountCluster.accounts),
                selectinload(AccountCluster.owner)
            )
        )
        clusters = result.scalars().all()
        
        return clusters, total
    
    async def update_cluster(
        self,
        cluster_id: str,
        **kwargs
    ) -> Optional[AccountCluster]:
        """Update a cluster's properties."""
        result = await self.db.execute(
            select(AccountCluster).where(AccountCluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        
        if not cluster:
            return None
        
        for key, value in kwargs.items():
            if hasattr(cluster, key):
                setattr(cluster, key, value)
        
        cluster.updated_at = datetime.utcnow()
        self.db.add(cluster)
        await self.db.commit()
        await self.db.refresh(cluster)
        
        return cluster
    
    async def delete_cluster(self, cluster_id: str) -> bool:
        """Delete a cluster and unassign its accounts."""
        result = await self.db.execute(
            select(AccountCluster).where(AccountCluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        
        if not cluster:
            return False
        
        # Unassign accounts from this cluster
        await self.db.execute(
            update(ExternalAccount)
            .where(ExternalAccount.cluster_id == cluster_id)
            .values(cluster_id=None)
        )
        
        # Delete connections involving this cluster
        await self.db.execute(
            delete(ClusterConnection).where(
                or_(
                    ClusterConnection.cluster_a_id == cluster_id,
                    ClusterConnection.cluster_b_id == cluster_id
                )
            )
        )
        
        # Delete the cluster
        await self.db.delete(cluster)
        await self.db.commit()
        
        return True
    
    async def create_connection(
        self,
        cluster_a_id: str,
        cluster_b_id: str,
        connection_type: ConnectionTypeEnum = ConnectionTypeEnum.SAME_PERSON,
        confidence: float = 0.5,
        created_by_id: Optional[str] = None,
        evidence: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ClusterConnection:
        """
        Create a manual connection between two clusters.
        
        Args:
            cluster_a_id: First cluster ID
            cluster_b_id: Second cluster ID
            connection_type: Type of connection
            confidence: Confidence level (0-1)
            created_by_id: Internal user who created this connection
            evidence: Evidence supporting the connection
            notes: Additional notes
            
        Returns:
            ClusterConnection instance
        """
        result = await self.db.execute(
            select(ClusterConnection).where(
                or_(
                    and_(
                        ClusterConnection.cluster_a_id == cluster_a_id,
                        ClusterConnection.cluster_b_id == cluster_b_id
                    ),
                    and_(
                        ClusterConnection.cluster_a_id == cluster_b_id,
                        ClusterConnection.cluster_b_id == cluster_a_id
                    )
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.connection_type = connection_type
            existing.confidence = confidence
            existing.evidence = evidence
            existing.notes = notes
            existing.updated_at = datetime.utcnow()
            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        
        connection = ClusterConnection(
            id=str(uuid.uuid4()),
            cluster_a_id=cluster_a_id,
            cluster_b_id=cluster_b_id,
            connection_type=connection_type,
            confidence=confidence,
            created_by_id=created_by_id,
            evidence=evidence,
            notes=notes,
            status=ConnectionStatusEnum.PROPOSED
        )
        self.db.add(connection)
        await self.db.commit()
        await self.db.refresh(connection)
        
        return connection
    
    async def get_connections(
        self,
        cluster_id: Optional[str] = None,
        status: Optional[ConnectionStatusEnum] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[ClusterConnection], int]:
        """Get cluster connections with optional filtering."""
        query = select(ClusterConnection)
        count_query = select(func.count()).select_from(ClusterConnection)
        
        conditions = []
        if cluster_id:
            conditions.append(
                or_(
                    ClusterConnection.cluster_a_id == cluster_id,
                    ClusterConnection.cluster_b_id == cluster_id
                )
            )
        if status:
            conditions.append(ClusterConnection.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        query = query.order_by(ClusterConnection.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(
            query.options(
                joinedload(ClusterConnection.cluster_a),
                joinedload(ClusterConnection.cluster_b),
                joinedload(ClusterConnection.created_by)
            )
        )
        connections = result.scalars().all()
        
        return connections, total
    
    async def confirm_connection(self, connection_id: str, user_id: str) -> bool:
        """Confirm a proposed connection."""
        result = await self.db.execute(
            select(ClusterConnection).where(ClusterConnection.id == connection_id)
        )
        connection = result.scalar_one_or_none()
        
        if not connection:
            return False
        
        connection.status = ConnectionStatusEnum.CONFIRMED
        connection.verified_at = datetime.utcnow()
        connection.verified_by_id = user_id
        self.db.add(connection)
        await self.db.commit()
        
        return True
    
    async def get_account(self, account_id: str) -> Optional[ExternalAccount]:
        """Get an external account by ID with cluster info."""
        result = await self.db.execute(
            select(ExternalAccount)
            .where(ExternalAccount.id == account_id)
            .options(
                joinedload(ExternalAccount.cluster),
                joinedload(ExternalAccount.comments)
            )
        )
        return result.scalar_one_or_none()
    
    async def get_accounts(
        self,
        cluster_id: Optional[str] = None,
        platform: Optional[PlatformEnum] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[ExternalAccount], int]:
        """Get external accounts with optional filtering."""
        query = select(ExternalAccount)
        count_query = select(func.count()).select_from(ExternalAccount)
        
        conditions = []
        if cluster_id:
            conditions.append(ExternalAccount.cluster_id == cluster_id)
        if platform:
            conditions.append(ExternalAccount.platform == platform)
        if search:
            conditions.append(
                or_(
                    ExternalAccount.username.ilike(f"%{search}%"),
                    ExternalAccount.display_name.ilike(f"%{search}%")
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        query = query.order_by(ExternalAccount.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(
            query.options(
                joinedload(ExternalAccount.cluster),
                joinedload(ExternalAccount.comments)
            )
        )
        accounts = result.scalars().all()
        
        return accounts, total
    
    async def get_cluster_graph(self, cluster_id: Optional[str] = None) -> dict:
        """
        Get cluster graph data for visualization.
        
        Returns a dict with nodes and links for D3.js or similar.
        """
        clusters_result = await self.db.execute(
            select(AccountCluster).options(
                selectinload(AccountCluster.accounts).selectinload(
                    ExternalAccount.comments
                )
            )
        )
        clusters = clusters_result.scalars().all()
        
        connections_result = await self.db.execute(
            select(ClusterConnection)
        )
        connections = connections_result.scalars().all()
        
        nodes = []
        cluster_map = {}
        
        for cluster in clusters:
            if cluster_id and cluster.id != cluster_id:
                # Only include connected clusters if cluster_id is specified
                connected = any(
                    c.cluster_a_id == cluster.id or c.cluster_b_id == cluster.id
                    for c in connections
                )
                if not connected:
                    continue
            
            cluster_map[cluster.id] = len(nodes)
            nodes.append({
                "id": cluster.id,
                "name": cluster.name,
                "type": "cluster",
                "cluster_type": cluster.cluster_type.value if hasattr(cluster.cluster_type, "value") else cluster.cluster_type,
                "comment_count": cluster.comment_count,
                "toxicity_score": cluster.toxicity_score,
                "color": cluster.color,
                "icon": cluster.icon,
                "index": len(nodes)
            })
            for account in cluster.accounts:
                nodes.append({
                    "id": account.id,
                    "name": account.username or account.display_name or "Unknown",
                    "type": "account",
                    "platform": account.platform.value if hasattr(account.platform, "value") else account.platform,
                    "cluster_id": cluster.id,
                    "comment_count": len(account.comments),
                    "color": cluster.color,
                    "index": len(nodes)
                })
        links = []

        for connection in connections:
            if cluster_id:
                if (connection.cluster_a_id != cluster_id and
                    connection.cluster_b_id != cluster_id):
                    continue

            links.append({
                "source": cluster_map.get(connection.cluster_a_id),
                "target": cluster_map.get(connection.cluster_b_id),
                "type": "connection",
                "connection_type": connection.connection_type.value if hasattr(connection.connection_type, "value") else connection.connection_type,
                "confidence": connection.confidence,
                "status": connection.status.value if hasattr(connection.status, "value") else connection.status
            })
        
        # Links from accounts to their clusters
        for cluster in clusters:
            if cluster_id and cluster.id != cluster_id:
                continue
            
            for account in cluster.accounts:
                account_index = None
                for i, node in enumerate(nodes):
                    if node["id"] == account.id:
                        account_index = i
                        break
                
                if account_index is not None:
                    links.append({
                        "source": account_index,
                        "target": cluster_map[cluster.id],
                        "type": "belongs_to"
                    })
        
        return {
            "nodes": nodes,
            "links": links
        }
    
    async def _update_cluster_metadata(self, cluster_id: str) -> None:
        """Update cluster metadata (comment count, toxicity score, etc.)."""
        result = await self.db.execute(
            select(AccountCluster).where(AccountCluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        
        if not cluster:
            return
        result = await self.db.execute(
            select(Comment)
            .options(selectinload(Comment.classifications))
            .join(ExternalAccount, Comment.external_account_id == ExternalAccount.id)
            .where(ExternalAccount.cluster_id == cluster_id)
        )
        comments = result.scalars().all()

        cluster.comment_count = len(comments)
        
        if comments:
            total_toxicity = 0
            count = 0
            for comment in comments:
                if comment.classifications:
                    for classification in comment.classifications:
                        total_toxicity += classification.harmful_score
                        count += 1
            if count > 0:
                cluster.toxicity_score = total_toxicity / count
        if comments:
            latest_comment = max(comments, key=lambda c: c.created_at)
            latest_at = latest_comment.created_at
            if latest_at.tzinfo is not None:
                latest_at = latest_at.replace(tzinfo=None)
            cluster.last_activity_at = latest_at
        
        self.db.add(cluster)
        await self.db.commit()
    
    async def assign_account_to_cluster(
        self,
        account_id: str,
        cluster_id: str
    ) -> bool:
        """Assign an account to a cluster."""
        result = await self.db.execute(
            select(ExternalAccount).where(ExternalAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            return False
        
        account.cluster_id = cluster_id
        self.db.add(account)
        await self.db.commit()
        await self._update_cluster_metadata(cluster_id)
        
        return True
    
    async def remove_account_from_cluster(self, account_id: str) -> bool:
        """Remove an account from its cluster."""
        result = await self.db.execute(
            select(ExternalAccount).where(ExternalAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        
        if not account or not account.cluster_id:
            return False
        
        cluster_id = account.cluster_id
        account.cluster_id = None
        self.db.add(account)
        await self.db.commit()
        await self._update_cluster_metadata(cluster_id)
        
        return True

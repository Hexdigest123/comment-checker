"""Tests for the cluster graph endpoint (platform -> cluster -> account -> comment)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AccountCluster,
    ClusterTypeEnum,
    Comment,
    DiscoveryMethodEnum,
    ExternalAccount,
    PlatformEnum,
    User,
)


async def _create_graph_data(db_session: AsyncSession, test_user: User) -> None:
    """Create one cluster with an Instagram and a YouTube account; one comment."""
    cluster = AccountCluster(
        id='cluster-1',
        name='Test Cluster',
        cluster_type=ClusterTypeEnum.BOT_NETWORK,
        discovery_method=DiscoveryMethodEnum.MANUAL,
    )
    db_session.add(cluster)
    await db_session.flush()

    instagram_account = ExternalAccount(
        id='account-ig',
        platform=PlatformEnum.INSTAGRAM,
        username='ig_user',
        cluster_id='cluster-1',
    )
    youtube_account = ExternalAccount(
        id='account-yt',
        platform=PlatformEnum.YOUTUBE,
        username='yt_user',
        cluster_id='cluster-1',
    )
    db_session.add_all([instagram_account, youtube_account])
    await db_session.flush()

    comment = Comment(
        id=3001,
        text='graph test comment',
        user_id=test_user.id,
        status='pending',
        external_account_id='account-ig',
    )
    db_session.add(comment)
    await db_session.commit()


class TestClusterGraph:
    """Tests for GET /api/v1/clusters/graph."""

    @pytest.mark.asyncio
    async def test_graph_includes_platform_nodes(
        self, client, db_session: AsyncSession, test_user: User
    ):
        """The graph contains platform, cluster, account and comment nodes."""
        await _create_graph_data(db_session, test_user)

        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']

        response = client.get(
            '/api/v1/clusters/graph',
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == 200
        nodes = response.json()['nodes']
        links = response.json()['links']

        by_type: dict = {}
        for node in nodes:
            by_type.setdefault(node['type'], []).append(node)
        assert set(by_type) == {'platform', 'cluster', 'account', 'comment'}

        # One platform node per distinct account platform
        platforms = {node['platform'] for node in by_type['platform']}
        assert platforms == {'instagram', 'youtube'}

        # Platform comment_count sums the comments of its accounts
        instagram = next(n for n in by_type['platform'] if n['platform'] == 'instagram')
        youtube = next(n for n in by_type['platform'] if n['platform'] == 'youtube')
        assert instagram['comment_count'] == 1
        assert youtube['comment_count'] == 0

        # Platform -> cluster links point at real platform and cluster nodes
        platform_links = [link for link in links if link['type'] == 'platform']
        assert len(platform_links) == 2
        for link in platform_links:
            assert nodes[link['source']]['type'] == 'platform'
            assert nodes[link['target']]['id'] == 'cluster-1'

        # The rest of the hierarchy is still linked
        assert any(link['type'] == 'belongs_to' for link in links)
        assert any(link['type'] == 'comment' for link in links)

    @pytest.mark.asyncio
    async def test_graph_unauthenticated(self, client):
        """The graph requires authentication."""
        response = client.get('/api/v1/clusters/graph')
        assert response.status_code == 401

"""Tests for the admin API endpoints."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AccountCluster,
    ClusterConnection,
    ClusterTypeEnum,
    Comment,
    CommentMention,
    ConnectionStatusEnum,
    ConnectionTypeEnum,
    DiscoveryMethodEnum,
    ExternalAccount,
    PlatformEnum,
    User,
)


async def _create_graph_data(db_session: AsyncSession, test_user: User) -> None:
    """Create two clusters, two accounts, one connection, one comment and one mention."""
    cluster_a = AccountCluster(
        id='cluster-a',
        name='Cluster A',
        cluster_type=ClusterTypeEnum.BOT_NETWORK,
        discovery_method=DiscoveryMethodEnum.MANUAL,
    )
    cluster_b = AccountCluster(
        id='cluster-b',
        name='Cluster B',
        cluster_type=ClusterTypeEnum.TROLL_FARM,
        discovery_method=DiscoveryMethodEnum.MANUAL,
    )
    db_session.add_all([cluster_a, cluster_b])
    await db_session.flush()

    account_a = ExternalAccount(
        id='account-a',
        platform=PlatformEnum.TWITTER,
        username='a_user',
        cluster_id='cluster-a',
    )
    account_b = ExternalAccount(
        id='account-b',
        platform=PlatformEnum.INSTAGRAM,
        username='b_user',
        cluster_id='cluster-b',
    )
    db_session.add_all([account_a, account_b])
    await db_session.flush()

    connection = ClusterConnection(
        id='connection-1',
        cluster_a_id='cluster-a',
        cluster_b_id='cluster-b',
        connection_type=ConnectionTypeEnum.COORDINATED,
        status=ConnectionStatusEnum.CONFIRMED,
    )
    comment = Comment(
        id=4001,
        text='admin test comment',
        user_id=test_user.id,
        status='pending',
        external_account_id='account-a',
    )
    db_session.add_all([connection, comment])
    await db_session.flush()

    mention = CommentMention(
        comment_id=comment.id,
        external_account_id='account-b',
        mentioned_username='b_user',
        platform='instagram',
    )
    db_session.add(mention)
    await db_session.commit()


def _login(client, username: str, password: str) -> str:
    login_response = client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': password},
    )
    return login_response.json()['access_token']


class TestWipeGraph:
    """Tests for DELETE /api/v1/admin/graph."""

    @pytest.mark.asyncio
    async def test_wipe_graph_requires_admin(
        self, client, db_session: AsyncSession, test_user: User
    ):
        """Non-admin users get 403."""
        await _create_graph_data(db_session, test_user)
        token = _login(client, test_user.username, 'testpassword')

        response = client.delete(
            '/api/v1/admin/graph',
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_wipe_graph_deletes_clusters_accounts_and_connections(
        self, client, db_session: AsyncSession, test_user: User, test_admin: User
    ):
        """The graph is emptied and comments are detached but kept."""
        await _create_graph_data(db_session, test_user)
        token = _login(client, test_admin.username, 'adminpassword')

        response = client.delete(
            '/api/v1/admin/graph',
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == 200
        body = response.json()
        assert body['deleted_clusters'] == 2
        assert body['deleted_accounts'] == 2
        assert body['deleted_connections'] == 1

        assert await db_session.scalar(select(func.count(AccountCluster.id))) == 0
        assert await db_session.scalar(select(func.count(ExternalAccount.id))) == 0
        assert await db_session.scalar(select(func.count(ClusterConnection.id))) == 0
        assert await db_session.scalar(select(func.count(CommentMention.comment_id))) == 0

        # Comments survive but are detached from their (deleted) authors.
        comment = await db_session.scalar(select(Comment).where(Comment.id == 4001))
        assert comment is not None
        assert comment.external_account_id is None

    @pytest.mark.asyncio
    async def test_wipe_graph_on_empty_database(
        self, client, db_session: AsyncSession, test_admin: User
    ):
        """Wiping an empty graph succeeds with zero counts."""
        token = _login(client, test_admin.username, 'adminpassword')

        response = client.delete(
            '/api/v1/admin/graph',
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == 200
        body = response.json()
        assert body['deleted_clusters'] == 0
        assert body['deleted_accounts'] == 0
        assert body['deleted_connections'] == 0

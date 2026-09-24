"""Tests for @mention extraction and linking to registered accounts."""

import pytest
import pytest_asyncio
import uuid

from src.db.models import ExternalAccount
from src.db.models.external_account import PlatformEnum as PE
from src.services.mentions import extract_mentions
from src.services.comment import create_comment


class TestExtractMentions:
    """Tests for @handle extraction from text."""

    def test_basic_mention(self):
        assert extract_mentions('hey @irf_cey look') == ['irf_cey']

    def test_multiple_mentions_preserve_order(self):
        assert extract_mentions('@bob and @alice') == ['bob', 'alice']

    def test_case_insensitive_deduplication(self):
        assert extract_mentions('@Irf_Cey told @irf_cey') == ['Irf_Cey']

    def test_trailing_punctuation_trimmed(self):
        assert extract_mentions('hello @irf_cey.') == ['irf_cey']
        assert extract_mentions('hello @bob_...') == ['bob']

    def test_email_not_a_mention(self):
        assert extract_mentions('mail me at user@test.com') == []

    def test_no_mention(self):
        assert extract_mentions('no mentions here') == []
        assert extract_mentions('') == []
        assert extract_mentions(None) == []

    def test_handle_with_digits_and_dots(self):
        assert extract_mentions('@user.name_123 ok') == ['user.name_123']


class TestMentionLinking:
    """Tests for linking mentions to registered accounts on the same platform."""

    @pytest_asyncio.fixture
    async def accounts(self, db_session):
        """Create registered accounts across platforms."""
        same_platform = ExternalAccount(
            id=str(uuid.uuid4()),
            platform=PE.INSTAGRAM,
            username='irf_cey',
        )
        other_platform = ExternalAccount(
            id=str(uuid.uuid4()),
            platform=PE.TWITTER,
            username='irf_cey',
        )
        other_user = ExternalAccount(
            id=str(uuid.uuid4()),
            platform=PE.INSTAGRAM,
            username='alice',
        )
        db_session.add_all([same_platform, other_platform, other_user])
        await db_session.commit()
        return same_platform, other_platform, other_user

    @pytest.mark.asyncio
    async def test_links_only_same_platform_registered_accounts(
        self, db_session, test_user, accounts
    ):
        """Only accounts registered on the comment's platform are linked."""
        same_platform, other_platform, other_user = accounts
        comment = await create_comment(
            db_session,
            {
                'text': 'hey @irf_cey and @alice and @nobody',
                'user_id': test_user.id,
                'platform': 'instagram',
                'status': 'pending',
            },
        )

        from sqlalchemy import select
        from src.db.models import CommentMention

        result = await db_session.execute(
            select(CommentMention).where(CommentMention.comment_id == comment.id)
        )
        rows = result.scalars().all()
        linked_ids = {r.external_account_id for r in rows}
        # twitter/irf_cey is a different platform; @nobody is unregistered
        assert linked_ids == {same_platform.id, other_user.id}
        assert other_platform.id not in linked_ids

    @pytest.mark.asyncio
    async def test_ignores_mention_without_platform(self, db_session, test_user, accounts):
        """Without a known platform, mentions are ignored (no same-platform check possible)."""
        comment = await create_comment(
            db_session,
            {
                'text': 'hey @irf_cey',
                'user_id': test_user.id,
                'status': 'pending',
            },
        )
        from sqlalchemy import select
        from src.db.models import CommentMention

        result = await db_session.execute(
            select(CommentMention).where(CommentMention.comment_id == comment.id)
        )
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_source_platform_fallback(self, db_session, test_user, accounts):
        """source_platform is used when platform is not set."""
        same_platform, _, _ = accounts
        comment = await create_comment(
            db_session,
            {
                'text': 'hey @irf_cey',
                'user_id': test_user.id,
                'source_platform': 'instagram',
                'status': 'pending',
            },
        )
        from sqlalchemy import select
        from src.db.models import CommentMention

        result = await db_session.execute(
            select(CommentMention).where(CommentMention.comment_id == comment.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].external_account_id == same_platform.id
        assert rows[0].mentioned_username == 'irf_cey'

    @pytest.mark.asyncio
    async def test_self_mention_ignored(self, db_session, test_user, accounts):
        """A comment does not reference its own author."""
        author, _, other_user = accounts
        comment = await create_comment(
            db_session,
            {
                'text': 'I am @irf_cey myself, but also @alice',
                'user_id': test_user.id,
                'platform': 'instagram',
                'external_account_id': author.id,
                'status': 'pending',
            },
        )
        from sqlalchemy import select
        from src.db.models import CommentMention

        result = await db_session.execute(
            select(CommentMention).where(CommentMention.comment_id == comment.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].external_account_id == other_user.id

    @pytest.mark.asyncio
    async def test_update_resyncs_mentions(self, db_session, test_user, accounts):
        """Updating the text recomputes the mention links."""
        from sqlalchemy import select
        from src.db.models import CommentMention
        from src.services.comment import update_comment
        from src.schemas import CommentUpdate

        same_platform, _, other_user = accounts
        comment = await create_comment(
            db_session,
            {
                'text': 'hey @irf_cey',
                'user_id': test_user.id,
                'platform': 'instagram',
                'status': 'pending',
            },
        )
        result = await db_session.execute(
            select(CommentMention).where(CommentMention.comment_id == comment.id)
        )
        assert len(result.scalars().all()) == 1

        await update_comment(
            db_session,
            comment.id,
            CommentUpdate(text='now I talk to @alice instead'),
        )
        result = await db_session.execute(
            select(CommentMention).where(CommentMention.comment_id == comment.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].external_account_id == other_user.id


class TestMentionsAPI:
    """Tests for mentions in the comments API."""

    @pytest.mark.asyncio
    async def test_get_comment_includes_mentions(self, client, db_session, test_user):
        """The comment detail response lists resolved mentions."""
        account = ExternalAccount(
            id=str(uuid.uuid4()),
            platform=PE.INSTAGRAM,
            username='irf_cey',
        )
        db_session.add(account)
        await db_session.commit()

        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']

        create_response = client.post(
            '/api/v1/comments',
            json={
                'text': 'reply to @irf_cey and @unknown_user',
                'source_platform': 'instagram',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        assert create_response.status_code == 201
        data = create_response.json()
        assert data['mentions'] is not None
        assert len(data['mentions']) == 1
        assert data['mentions'][0]['account_id'] == account.id
        assert data['mentions'][0]['username'] == 'irf_cey'
        assert data['mentions'][0]['platform'] == 'instagram'
        assert data['mentions'][0]['mentioned_username'] == 'irf_cey'

        get_response = client.get(
            f'/api/v1/comments/{data["id"]}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert get_response.status_code == 200
        assert get_response.json()['mentions'][0]['account_id'] == account.id

    @pytest.mark.asyncio
    async def test_unregistered_mention_ignored_in_response(self, client, test_user):
        """Mentions of unregistered accounts do not appear in the response."""
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']

        create_response = client.post(
            '/api/v1/comments',
            json={
                'text': 'shoutout to @not_in_system',
                'source_platform': 'instagram',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        assert create_response.status_code == 201
        assert create_response.json()['mentions'] is None

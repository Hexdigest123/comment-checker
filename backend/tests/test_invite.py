"""Tests for invite and password reset endpoints."""

import pytest
from datetime import datetime, timedelta

from src.models import User, InviteToken
from src.utils.security import get_password_hash


class TestInviteCreate:
    """Tests for creating invite tokens."""

    @pytest.mark.asyncio
    async def test_create_invite_admin(self, client, test_admin: User):
        """Test creating invite as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.post(
            '/invites',
            json={'email': 'newuser@example.com'},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data['email'] == 'newuser@example.com'
        assert 'token' in data

    @pytest.mark.asyncio
    async def test_create_invite_non_admin(self, client, test_user: User):
        """Test creating invite as non-admin."""
        # Login as regular user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.post(
            '/invites',
            json={'email': 'newuser@example.com'},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-admin users should not be able to create invites
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_invite_unauthenticated(self, client):
        """Test creating invite when not authenticated."""
        response = client.post('/invites', json={'email': 'newuser@example.com'})
        assert response.status_code == 401


class TestInviteList:
    """Tests for listing invite tokens."""

    @pytest.mark.asyncio
    async def test_list_invites_admin(self, client, test_admin: User, test_invite_token: InviteToken):
        """Test listing invites as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/invites',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_invites_non_admin(self, client, test_user: User):
        """Test listing invites as non-admin."""
        # Login as regular user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/invites',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-admin users should not be able to list invites
        assert response.status_code == 403


class TestInviteUse:
    """Tests for using invite tokens."""

    @pytest.mark.asyncio
    async def test_use_invite_valid(self, client, test_invite_token: InviteToken):
        """Test using a valid invite token."""
        response = client.post(
            f'/invites/{test_invite_token.token}/use',
            json={
                'name': 'New User',
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert 'access_token' in data
        assert 'user' in data

    @pytest.mark.asyncio
    async def test_use_invite_invalid_token(self, client):
        """Test using an invalid invite token."""
        response = client.post(
            '/invites/invalid-token/use',
            json={
                'name': 'New User',
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_use_invite_already_used(self, client, db_session, test_admin: User):
        """Test using an already used invite token."""
        # Create used invite
        invite = InviteToken(
            id='40000000-0000-0000-0000-000000000002',
            token='used-invite-token',
            email='used@example.com',
            is_used=True,
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_by=test_admin.id,
            created_at=datetime.utcnow(),
        )
        db_session.add(invite)
        await db_session.commit()
        
        response = client.post(
            f'/invites/{invite.token}/use',
            json={
                'name': 'New User',
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_use_invite_expired(self, client, db_session, test_admin: User):
        """Test using an expired invite token."""
        # Create expired invite
        invite = InviteToken(
            id='40000000-0000-0000-0000-000000000003',
            token='expired-invite-token',
            email='expired@example.com',
            is_used=False,
            expires_at=datetime.utcnow() - timedelta(days=1),
            created_by=test_admin.id,
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(invite)
        await db_session.commit()
        
        response = client.post(
            f'/invites/{invite.token}/use',
            json={
                'name': 'New User',
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 400


class TestInviteDelete:
    """Tests for deleting invite tokens."""

    @pytest.mark.asyncio
    async def test_delete_invite_admin(self, client, test_admin: User, test_invite_token: InviteToken):
        """Test deleting invite as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            f'/invites/{test_invite_token.token}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_invite_non_admin(self, client, test_user: User, test_invite_token: InviteToken):
        """Test deleting invite as non-admin."""
        # Login as regular user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            f'/invites/{test_invite_token.token}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-admin users should not be able to delete invites
        assert response.status_code == 403


class TestPasswordReset:
    """Tests for password reset functionality."""

    @pytest.mark.asyncio
    async def test_request_password_reset(self, client, test_user: User):
        """Test requesting a password reset."""
        response = client.post(
            '/password-reset/request',
            json={'email': test_user.email},
        )
        
        assert response.status_code == 200
        assert response.json()['message'] == 'Password reset link sent'

    @pytest.mark.asyncio
    async def test_confirm_password_reset(self, client, test_user: User, db_session):
        """Test confirming a password reset."""
        # Create a password reset token
        from src.models import PasswordResetToken
        token = PasswordResetToken(
            id='50000000-0000-0000-0000-000000000001',
            token='reset-token',
            user_id=test_user.id,
            is_used=False,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow(),
        )
        db_session.add(token)
        await db_session.commit()
        
        response = client.post(
            '/password-reset/confirm',
            json={
                'token': token.token,
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 200
        assert response.json()['message'] == 'Password reset successful'

    @pytest.mark.asyncio
    async def test_confirm_password_reset_invalid_token(self, client):
        """Test confirming password reset with invalid token."""
        response = client.post(
            '/password-reset/confirm',
            json={
                'token': 'invalid-token',
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_confirm_password_reset_used_token(self, client, db_session, test_user: User):
        """Test confirming password reset with used token."""
        # Create a used password reset token
        from src.models import PasswordResetToken
        token = PasswordResetToken(
            id='50000000-0000-0000-0000-000000000002',
            token='used-reset-token',
            user_id=test_user.id,
            is_used=True,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow(),
        )
        db_session.add(token)
        await db_session.commit()
        
        response = client.post(
            '/password-reset/confirm',
            json={
                'token': token.token,
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_confirm_password_reset_expired_token(self, client, db_session, test_user: User):
        """Test confirming password reset with expired token."""
        # Create an expired password reset token
        from src.models import PasswordResetToken
        token = PasswordResetToken(
            id='50000000-0000-0000-0000-000000000003',
            token='expired-reset-token',
            user_id=test_user.id,
            is_used=False,
            expires_at=datetime.utcnow() - timedelta(hours=1),
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        db_session.add(token)
        await db_session.commit()
        
        response = client.post(
            '/password-reset/confirm',
            json={
                'token': token.token,
                'password': 'newpassword',
            },
        )
        
        assert response.status_code == 400

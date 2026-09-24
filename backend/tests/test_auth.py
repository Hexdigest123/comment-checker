"""Tests for authentication endpoints."""

import pytest
from datetime import datetime, timedelta

from src.db.models import User, RefreshToken
from src.services.auth import get_password_hash, verify_password


class TestAuthLogin:
    """Tests for the login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user: User):
        """Test successful login with correct credentials."""
        response = client.post(
            '/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert 'token_type' in data
        assert data['token_type'] == 'bearer'
        assert 'user' in data
        assert data['user']['username'] == test_user.username

    @pytest.mark.asyncio
    async def test_login_invalid_username(self, client):
        """Test login with invalid username."""
        response = client.post(
            '/auth/login',
            json={'username': 'nonexistent', 'password': 'password'},
        )
        
        assert response.status_code == 401
        assert 'detail' in response.json()

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, test_user: User):
        """Test login with invalid password."""
        response = client.post(
            '/auth/login',
            json={'username': test_user.username, 'password': 'wrongpassword'},
        )
        
        assert response.status_code == 401
        assert 'detail' in response.json()

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, db_session):
        """Test login with inactive user."""
        password_hash = get_password_hash('password')
        user = User(
            id='00000000-0000-0000-0000-000000000010',
            username='inactive',
            name='Inactive User',
            password_hash=password_hash,
            is_admin=False,
            is_active=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.commit()

        response = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'password'},
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        """Test login with missing fields."""
        response = client.post('/auth/login', json={'username': 'testuser'})
        assert response.status_code == 422
        
        response = client.post('/auth/login', json={'password': 'password'})
        assert response.status_code == 422


class TestAuthMe:
    """Tests for the current user endpoint."""

    @pytest.mark.asyncio
    async def test_me_authenticated(self, client, test_user: User):
        """Test getting current user when authenticated."""
        # Login first
        login_response = client.post(
            '/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        # Get current user
        response = client.get(
            '/auth/me',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'user' in data
        assert data['user']['username'] == test_user.username

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, client):
        """Test getting current user when not authenticated."""
        response = client.get('/auth/me')
        assert response.status_code == 401


class TestAuthRefresh:
    """Tests for the token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, client, test_user: User, test_refresh_token: RefreshToken):
        """Test refreshing access token with valid refresh token."""
        response = client.post(
            '/auth/refresh',
            json={'refresh_token': test_refresh_token.token},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert 'token_type' in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client):
        """Test refreshing with invalid token."""
        response = client.post(
            '/auth/refresh',
            json={'refresh_token': 'invalid-token'},
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_expired_token(self, client, test_expired_refresh_token: RefreshToken):
        """Test refreshing with expired token."""
        response = client.post(
            '/auth/refresh',
            json={'refresh_token': test_expired_refresh_token.token},
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_revoked_token(self, client, db_session, test_user: User):
        """Test refreshing with revoked token."""
        token = RefreshToken(
            id='30000000-0000-0000-0000-000000000003',
            token='revoked-token',
            user_id=test_user.id,
            expires_at=datetime.utcnow() + timedelta(days=7),
            is_revoked=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(token)
        await db_session.commit()

        response = client.post(
            '/auth/refresh',
            json={'refresh_token': token.token},
        )
        
        assert response.status_code == 401


class TestAuthLogout:
    """Tests for the logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client, test_user: User, test_refresh_token: RefreshToken):
        """Test successful logout."""
        # Login first
        login_response = client.post(
            '/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        access_token = login_response.json()['access_token']
        
        # Logout
        response = client.post(
            '/auth/logout',
            headers={'Authorization': f'Bearer {access_token}'},
            json={'refresh_token': test_refresh_token.token},
        )
        
        assert response.status_code == 200
        assert response.json()['message'] == 'Successfully logged out'

    @pytest.mark.asyncio
    async def test_logout_unauthenticated(self, client):
        """Test logout when not authenticated."""
        response = client.post('/auth/logout')
        assert response.status_code == 401


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_get_password_hash(self):
        """Test password hashing."""
        password = 'testpassword'
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password(self):
        """Test password verification."""
        password = 'testpassword'
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password('wrongpassword', hashed) is False

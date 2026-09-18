"""Tests for user endpoints."""

import pytest
from datetime import datetime

from src.models import User
from src.utils.security import get_password_hash


class TestUsersList:
    """Tests for listing users."""

    @pytest.mark.asyncio
    async def test_list_users_admin(self, client, test_admin: User):
        """Test listing users as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/users',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert 'total' in data

    @pytest.mark.asyncio
    async def test_list_users_non_admin(self, client, test_user: User):
        """Test listing users as non-admin."""
        # Login as regular user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/users',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-admin users should not be able to list users
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_unauthenticated(self, client):
        """Test listing users when not authenticated."""
        response = client.get('/users')
        assert response.status_code == 401


class TestUsersCreate:
    """Tests for creating users."""

    @pytest.mark.asyncio
    async def test_create_user_admin(self, client, test_admin: User):
        """Test creating user as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.post(
            '/users',
            json={
                'email': 'newuser@example.com',
                'name': 'New User',
                'password': 'newpassword',
                'is_admin': False,
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data['email'] == 'newuser@example.com'
        assert data['name'] == 'New User'

    @pytest.mark.asyncio
    async def test_create_user_non_admin(self, client, test_user: User):
        """Test creating user as non-admin."""
        # Login as regular user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.post(
            '/users',
            json={
                'email': 'newuser@example.com',
                'name': 'New User',
                'password': 'newpassword',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-admin users should not be able to create users
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, client, test_admin: User):
        """Test creating user with duplicate email."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.post(
            '/users',
            json={
                'email': test_admin.email,
                'name': 'Duplicate User',
                'password': 'password',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 400


class TestUsersGet:
    """Tests for getting a specific user."""

    @pytest.mark.asyncio
    async def test_get_user_admin(self, client, test_admin: User, test_user: User):
        """Test getting user as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            f'/users/{test_user.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['email'] == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_self(self, client, test_user: User):
        """Test getting own user info."""
        # Login as user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            f'/users/{test_user.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_user_other_non_admin(self, client, test_user: User, db_session):
        """Test getting another user's info as non-admin."""
        # Create another user
        password_hash = get_password_hash('password')
        other_user = User(
            id='00000000-0000-0000-0000-000000000020',
            email='other@example.com',
            name='Other User',
            password_hash=password_hash,
            is_admin=False,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(other_user)
        await db_session.commit()
        
        # Login as user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            f'/users/{other_user.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-admin users should not be able to get other users
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client, test_admin: User):
        """Test getting non-existent user."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/users/00000000-0000-0000-0000-000000000099',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 404


class TestUsersUpdate:
    """Tests for updating users."""

    @pytest.mark.asyncio
    async def test_update_user_self(self, client, test_user: User):
        """Test updating own user info."""
        # Login as user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.put(
            f'/users/{test_user.id}',
            json={'name': 'Updated Name', 'email': test_user.email},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['name'] == 'Updated Name'

    @pytest.mark.asyncio
    async def test_update_user_admin(self, client, test_admin: User, test_user: User):
        """Test updating user as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.put(
            f'/users/{test_user.id}',
            json={'name': 'Updated Name', 'is_admin': True},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, client, test_admin: User):
        """Test updating non-existent user."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.put(
            '/users/00000000-0000-0000-0000-000000000099',
            json={'name': 'Updated Name'},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 404


class TestUsersDelete:
    """Tests for deleting users."""

    @pytest.mark.asyncio
    async def test_delete_user_admin(self, client, test_admin: User, test_user: User):
        """Test deleting user as admin."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            f'/users/{test_user.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        
        # Verify user is deleted
        response = client.get(
            f'/users/{test_user.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_self(self, client, test_user: User):
        """Test deleting own user."""
        # Login as user
        login_response = client.post(
            '/auth/login',
            json={'email': test_user.email, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            f'/users/{test_user.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Users should not be able to delete themselves
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, client, test_admin: User):
        """Test deleting non-existent user."""
        # Login as admin
        login_response = client.post(
            '/auth/login',
            json={'email': test_admin.email, 'password': 'adminpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            '/users/00000000-0000-0000-0000-000000000099',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 404

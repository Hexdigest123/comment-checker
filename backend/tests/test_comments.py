"""Tests for comment endpoints."""

import pytest
from datetime import datetime

from src.db.models import Comment, User
from src.services.auth import get_password_hash


class TestCommentsList:
    """Tests for listing comments."""

    @pytest.mark.asyncio
    async def test_list_comments_authenticated(self, client, test_user: User, test_comment: Comment):
        """Test listing comments when authenticated."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/api/v1/comments',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert 'total' in data

    @pytest.mark.asyncio
    async def test_list_comments_unauthenticated(self, client):
        """Test listing comments when not authenticated."""
        response = client.get('/api/v1/comments')
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_comments_with_filters(self, client, test_user: User, test_comment: Comment):
        """Test listing comments with filters."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        # Filter by status
        response = client.get(
            '/api/v1/comments?status=pending',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data


class TestCommentsCreate:
    """Tests for creating comments."""

    @pytest.mark.asyncio
    async def test_create_comment_authenticated(self, client, test_user: User):
        """Test creating comment when authenticated."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.post(
            '/api/v1/comments',
            json={
                'text': 'New comment text',
                'source_url': 'https://example.com/comment/2',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data['text'] == 'New comment text'
        assert data['status'] == 'pending'

    @pytest.mark.asyncio
    async def test_create_comment_unauthenticated(self, client):
        """Test creating comment when not authenticated."""
        response = client.post(
            '/api/v1/comments',
            json={'text': 'New comment text'},
        )
        assert response.status_code == 401


class TestCommentsGet:
    """Tests for getting a specific comment."""

    @pytest.mark.asyncio
    async def test_get_comment_authenticated(self, client, test_user: User, test_comment: Comment):
        """Test getting comment when authenticated."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            f'/api/v1/comments/{test_comment.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == test_comment.id

    @pytest.mark.asyncio
    async def test_get_comment_unauthenticated(self, client, test_comment: Comment):
        """Test getting comment when not authenticated."""
        response = client.get(f'/api/v1/comments/{test_comment.id}')
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_comment_not_found(self, client, test_user: User):
        """Test getting non-existent comment."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.get(
            '/api/v1/comments/999999',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 404


class TestCommentsUpdate:
    """Tests for updating comments."""

    @pytest.mark.asyncio
    async def test_update_comment_owner(self, client, test_user: User, test_comment: Comment):
        """Test updating comment as owner."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.put(
            f'/api/v1/comments/{test_comment.id}',
            json={'text': 'Updated comment text'},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['text'] == 'Updated comment text'

    @pytest.mark.asyncio
    async def test_update_comment_non_owner(self, client, test_user: User, db_session):
        """Test updating comment as non-owner."""
        # Create another user
        password_hash = get_password_hash('password')
        other_user = User(
            id=20,
            username='other',
            full_name='Other User',
            password_hash=password_hash,
            is_admin=False,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(other_user)
        await db_session.commit()
        
        # Create comment for other user
        comment = Comment(
            id=1002,
            text='Other comment',
            source_url='https://example.com/comment/2',
            user_id=other_user.id,
            status='pending',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(comment)
        await db_session.commit()
        
        # Login as test_user
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.put(
            f'/api/v1/comments/{comment.id}',
            json={'text': 'Updated comment text'},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-owner should not be able to update
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_comment_not_found(self, client, test_user: User):
        """Test updating non-existent comment."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.put(
            '/api/v1/comments/999999',
            json={'text': 'Updated comment text'},
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 404


class TestCommentsDelete:
    """Tests for deleting comments."""

    @pytest.mark.asyncio
    async def test_delete_comment_owner(self, client, test_user: User, test_comment: Comment):
        """Test deleting comment as owner."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            f'/api/v1/comments/{test_comment.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 204
        
        # Verify comment is deleted
        response = client.get(
            f'/api/v1/comments/{test_comment.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_comment_non_owner(self, client, test_user: User, db_session):
        """Test deleting comment as non-owner."""
        # Create another user
        password_hash = get_password_hash('password')
        other_user = User(
            id=20,
            username='other',
            full_name='Other User',
            password_hash=password_hash,
            is_admin=False,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(other_user)
        await db_session.commit()
        
        # Create comment for other user
        comment = Comment(
            id=1002,
            text='Other comment',
            source_url='https://example.com/comment/2',
            user_id=other_user.id,
            status='pending',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(comment)
        await db_session.commit()
        
        # Login as test_user
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            f'/api/v1/comments/{comment.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        # Non-owner should not be able to delete
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment_not_found(self, client, test_user: User):
        """Test deleting non-existent comment."""
        # Login
        login_response = client.post(
            '/api/v1/auth/login',
            json={'username': test_user.username, 'password': 'testpassword'},
        )
        token = login_response.json()['access_token']
        
        response = client.delete(
            '/api/v1/comments/999999',
            headers={'Authorization': f'Bearer {token}'},
        )
        
        assert response.status_code == 404

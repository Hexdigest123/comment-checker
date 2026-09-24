"""Pytest fixtures for Comment Checker backend."""

import os
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['JWT_SECRET'] = 'test-secret-key-for-testing-only'
os.environ['JWT_ALGORITHM'] = 'HS256'
os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'] = '30'
os.environ['REFRESH_TOKEN_EXPIRE_DAYS'] = '7'
os.environ['MISTRAL_API_KEY'] = 'test-api-key'
os.environ['FIRST_ADMIN_USERNAME'] = 'admin'
os.environ['FIRST_ADMIN_PASSWORD'] = 'admin'
os.environ['CORS_ORIGINS'] = '*'
os.environ['DEBUG'] = 'true'

from src.main import app
from src.db.base import Base
from src.db.session import get_db
from src.db.models import User, RefreshToken, Comment, Classification
from src.services.auth import get_password_hash

# Create test database engine
test_engine = create_async_engine(
    'sqlite+aiosqlite:///:memory:',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)

# Create test session factory
async_session = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Fixture to create all tables
@pytest.fixture(scope='session', autouse=True)
def create_tables() -> Generator[None, None, None]:
    """Create all database tables before tests and drop them after."""
    
    async def _create_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def _drop_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    # Run sync code in async context
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_create_tables())
    
    yield
    
    loop.run_until_complete(_drop_tables())


# Fixture to provide database session
@pytest.fixture(scope='function')
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test."""
    async with async_session() as session:
        yield session
        await session.rollback()
        await session.close()


# Fixture for FastAPI TestClient
@pytest.fixture(scope='function')
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client with database session."""
    
    def get_test_db() -> AsyncSession:
        return db_session
    
    app.dependency_overrides[get_db] = get_test_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# Fixture to create a test user
@pytest.fixture(scope='function')
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database."""
    password_hash = get_password_hash('testpassword')
    user = User(
        id='00000000-0000-0000-0000-000000000001',
        username='testuser',
        name='Test User',
        password_hash=password_hash,
        is_admin=False,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# Fixture to create a test admin user
@pytest.fixture(scope='function')
async def test_admin(db_session: AsyncSession) -> User:
    """Create a test admin user in the database."""
    password_hash = get_password_hash('adminpassword')
    user = User(
        id='00000000-0000-0000-0000-000000000002',
        username='admin',
        name='Admin User',
        password_hash=password_hash,
        is_admin=True,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# Fixture to create a test comment
@pytest.fixture(scope='function')
async def test_comment(db_session: AsyncSession, test_user: User) -> Comment:
    """Create a test comment in the database."""
    comment = Comment(
        id='10000000-0000-0000-0000-000000000001',
        text='This is a test comment',
        source_url='https://example.com/comment/1',
        user_id=test_user.id,
        status='pending',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


# Fixture to create a test classification
@pytest.fixture(scope='function')
async def test_classification(db_session: AsyncSession, test_comment: Comment) -> Classification:
    """Create a test classification in the database."""
    classification = Classification(
        id='20000000-0000-0000-0000-000000000001',
        comment_id=test_comment.id,
        backend='typesafe',
        category='safe',
        severity='low',
        confidence=0.95,
        harmful_score=0.05,
        details={},
        created_at=datetime.utcnow(),
    )
    db_session.add(classification)
    await db_session.commit()
    await db_session.refresh(classification)
    return classification


# Fixture to create an expired refresh token
@pytest.fixture(scope='function')
async def test_expired_refresh_token(db_session: AsyncSession, test_user: User) -> RefreshToken:
    """Create an expired refresh token."""
    token = RefreshToken(
        id='30000000-0000-0000-0000-000000000001',
        token='expired-token',
        user_id=test_user.id,
        expires_at=datetime.utcnow() - timedelta(days=1),
        is_revoked=False,
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


# Fixture to create a valid refresh token
@pytest.fixture(scope='function')
async def test_refresh_token(db_session: AsyncSession, test_user: User) -> RefreshToken:
    """Create a valid refresh token."""
    token = RefreshToken(
        id='30000000-0000-0000-0000-000000000002',
        token='valid-token',
        user_id=test_user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
        is_revoked=False,
        created_at=datetime.utcnow(),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token

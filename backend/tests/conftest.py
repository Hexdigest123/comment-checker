"""Pytest fixtures for Comment Checker backend."""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
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
from src.db.session import get_async_db
from src.db.models import User, RefreshToken, TokenStatus, Comment, Classification
from src.services.token import hash_token
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
        # comment_embeddings uses a Postgres ARRAY (PGVector) column that
        # SQLite cannot compile; tests do not exercise embeddings.
        tables = [t for name, t in Base.metadata.tables.items() if name != 'comment_embeddings']
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=tables)

    async def _drop_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    # Run sync code in async context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_create_tables())

    yield

    loop.run_until_complete(_drop_tables())
    loop.close()
    asyncio.set_event_loop(None)


# Fixture to provide database session
@pytest_asyncio.fixture(scope='function')
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test."""
    async with async_session() as session:
        yield session
        await session.rollback()
        # Tables live for the whole session; clear committed rows so
        # function-scoped fixtures with fixed IDs do not collide.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == 'comment_embeddings':
                continue
            await session.execute(table.delete())
        await session.commit()
        await session.close()


# Fixture for FastAPI TestClient
@pytest.fixture(scope='function')
def client(db_session: AsyncSession, monkeypatch) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client with database session."""

    def get_test_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_async_db] = get_test_db

    # Tables are created by the create_tables fixture; the app's own
    # init_db() would fail on the Postgres-only comment_embeddings table,
    # and the background worker must not run during tests. Startup admin
    # bootstrap is skipped too: it would run on the app engine, which is
    # a separate empty in-memory database in tests.
    import src.main as main_module
    async def _noop_init_db() -> None:
        return None
    async def _noop_first_admin() -> None:
        return None
    monkeypatch.setattr(main_module, 'init_db', _noop_init_db)
    monkeypatch.setattr(main_module, 'create_first_admin_on_startup', _noop_first_admin)
    monkeypatch.setattr(main_module.settings, 'worker_enabled', False)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# Fixture to create a test user
@pytest_asyncio.fixture(scope='function')
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database."""
    password_hash = get_password_hash('testpassword')
    user = User(
        id=1,
        username='testuser',
        full_name='Test User',
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
@pytest_asyncio.fixture(scope='function')
async def test_admin(db_session: AsyncSession) -> User:
    """Create a test admin user in the database."""
    password_hash = get_password_hash('adminpassword')
    user = User(
        id=2,
        username='admin',
        full_name='Admin User',
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
@pytest_asyncio.fixture(scope='function')
async def test_comment(db_session: AsyncSession, test_user: User) -> Comment:
    """Create a test comment in the database."""
    comment = Comment(
        id=1001,
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
@pytest_asyncio.fixture(scope='function')
async def test_classification(db_session: AsyncSession, test_comment: Comment) -> Classification:
    """Create a test classification in the database."""
    classification = Classification(
        id=2001,
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
@pytest_asyncio.fixture(scope='function')
async def test_expired_refresh_token(db_session: AsyncSession, test_user: User) -> RefreshToken:
    """Create an expired refresh token."""
    token = RefreshToken(
        id=3001,
        token='expired-token',
        token_hash=hash_token('expired-token'),
        user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        status=TokenStatus.EXPIRED,
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


# Fixture to create a valid refresh token
@pytest_asyncio.fixture(scope='function')
async def test_refresh_token(db_session: AsyncSession, test_user: User) -> RefreshToken:
    """Create a valid refresh token."""
    token = RefreshToken(
        id=3002,
        token='valid-token',
        token_hash=hash_token('valid-token'),
        user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        status=TokenStatus.ACTIVE,
        created_at=datetime.utcnow(),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token

"""
Database session management
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .base import Base
from ..config import get_database_settings

settings = get_database_settings()
_engine_kwargs: dict = {
    "pool_size": settings.pool_size,
    "max_overflow": settings.max_overflow,
    "pool_timeout": settings.pool_timeout,
    "pool_recycle": settings.pool_recycle,
    "pool_pre_ping": settings.pool_pre_ping,
    "echo": False,
}
if settings.async_database_url.startswith("sqlite"):
    _engine_kwargs = {"echo": False}

async_engine = create_async_engine(
    settings.async_database_url,
    **_engine_kwargs,
)

async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session dependency for FastAPI.
    Automatically commits on success, rolls back on error.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.
    Called on application startup.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.
    Called on application shutdown.
    """
    await async_engine.dispose()

"""
Database configuration
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """
    Database configuration settings.
    Supports both DATABASE_URL and individual connection parameters.
    """

    # Connection URL (takes precedence if provided)
    database_url: Optional[str] = None

    # Individual connection parameters
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "comment_checker"
    db_user: str = "comment_checker"
    db_password: str = "your_secure_db_password_here"

    # Pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True

    # Async settings
    async_driver: str = "asyncpg"

    # Model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        """Construct async database URL from individual settings."""
        if self.database_url:
            # Replace sync driver with async if needed
            url = self.database_url
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://")
            elif url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://")
            return url
        return f"postgresql+{self.async_driver}://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def sync_database_url(self) -> str:
        """Construct sync database URL from individual settings."""
        if self.database_url:
            url = self.database_url
            if url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql+asyncpg://", "postgresql://")
            return url
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache()
def get_database_settings() -> DatabaseSettings:
    """Get cached database settings instance."""
    return DatabaseSettings()

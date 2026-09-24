"""
Application settings using Pydantic Settings
"""

import json
from functools import lru_cache
from typing import Annotated, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Comment Checker"
    app_version: str = "1.0.0"
    debug: bool = False
    production: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # NoDecode: accept comma-separated strings from env files (parsed in validator)
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ],
        description="Allowed CORS origins",
    )

    jwt_secret_key: str = Field(
        ...,
        description="JWT Secret Key - Generate with: openssl rand -hex 32",
        min_length=32,
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # First Admin (auto-created on first startup; the only user of the app)
    first_admin_username: str = "admin"
    first_admin_password: str = Field(
        ...,
        description="First admin password",
    )

    # External API Keys
    mistral_api_key: Optional[str] = None

    # ExportComments.com API (direct URL import)
    exportcomments_api_key: Optional[str] = None

    # Embeddings
    generate_embeddings: bool = True

    # Classification worker (job queue that processes PENDING comments)
    worker_enabled: bool = True
    worker_poll_interval_seconds: float = 2.0
    worker_batch_size: int = 10

    # Classification Configuration
    classification_threshold: float = 0.3

    # CSV Processing
    max_csv_size_mb: int = 50
    csv_delimiter: str = ","

    # Dashboard Configuration
    dashboard_default_range: str = "1y"

    # Logging
    log_level: str = "INFO"

    # Security Headers
    hsts_max_age: int = 31536000
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    csp_default_src: str = "'self'"
    csp_script_src: str = "'self' 'unsafe-inline'"
    csp_style_src: str = "'self' 'unsafe-inline'"
    csp_img_src: str = "'self' data: http: https:"
    csp_font_src: str = "'self'"
    csp_connect_src: str = "'self'"
    frame_options: str = "DENY"
    x_content_type_options: str = "nosniff"
    x_xss_protection: str = "1; mode=block"

    # Model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret_key(cls, v: Optional[str]) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. "
                "Generate with: openssl rand -hex 32"
            )
        return v

    @field_validator("dashboard_default_range", mode="before")
    @classmethod
    def validate_dashboard_range(cls, v: Optional[str]) -> str:
        valid_ranges = ["1m", "6m", "1y", "all"]
        if v and v.lower() not in valid_ranges:
            raise ValueError(f"DASHBOARD_DEFAULT_RANGE must be one of {valid_ranges}")
        return v.lower() if v else "1y"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

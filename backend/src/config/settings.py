"""
Application settings using Pydantic Settings
OWASP-compliant security configurations
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with OWASP-compliant defaults.
    All sensitive values should be loaded from environment variables.
    """

    # Application
    app_name: str = "Comment Checker"
    app_version: str = "1.0.0"
    debug: bool = False
    production: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS - OWASP: Restrict origins to known values
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ],
        description="Allowed CORS origins",
    )

    # Authentication - OWASP: Use strong JWT configuration
    jwt_secret_key: str = Field(
        ...,
        description="JWT Secret Key - Generate with: openssl rand -hex 32",
        min_length=32,
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Password hashing - OWASP: Use bcrypt with cost factor >= 12
    bcrypt_cost_factor: int = Field(
        default=12,
        ge=12,
        le=14,
        description="Bcrypt cost factor (12-14 recommended)",
    )

    # First Admin (auto-created on first startup)
    first_admin_email: str = "admin@localhost"
    first_admin_password: str = Field(
        ...,
        description="First admin password",
        min_length=8,
    )

    # Email Configuration
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = False
    email_from: str = "noreply@comment-checker.local"
    email_from_name: str = "Comment Checker"

    # External API Keys
    typesafe_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None

    # Classification Configuration
    default_backend: str = "typesafe"  # typesafe, mistral, or combined
    classification_threshold: float = 0.3
    max_comments_per_request: int = 100

    # CSV Processing
    max_csv_size_mb: int = 50
    csv_delimiter: str = ","

    # Dashboard Configuration
    dashboard_default_range: str = "1y"
    pagination_options: List[int] = [5, 10, 15, 25]
    default_pagination: int = 10

    # Rate Limiting - OWASP: Implement rate limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

    # Logging
    log_level: str = "INFO"

    # Security Headers - OWASP recommendations
    hsts_max_age: int = 31536000  # 1 year
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

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret_key(cls, v: Optional[str]) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. "
                "Generate with: openssl rand -hex 32"
            )
        return v

    @field_validator("first_admin_password", mode="before")
    @classmethod
    def validate_first_admin_password(cls, v: Optional[str]) -> str:
        if not v or len(v) < 8:
            raise ValueError("FIRST_ADMIN_PASSWORD must be at least 8 characters")
        return v

    @field_validator("default_backend", mode="before")
    @classmethod
    def validate_backend(cls, v: Optional[str]) -> str:
        valid_backends = ["typesafe", "mistral", "combined"]
        if v and v.lower() not in valid_backends:
            raise ValueError(f"BACKEND must be one of {valid_backends}")
        return v.lower() if v else "typesafe"

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

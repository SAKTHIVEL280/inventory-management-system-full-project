"""Backend configuration."""
import os
from urllib.parse import urlparse

from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings read from environment variables."""

    # Database
    database_url: str

    @field_validator("database_url")
    @classmethod
    def validate_postgres_only(cls, value: str) -> str:
        """Enforce PostgreSQL-only database URLs."""
        v = (value or "").strip()
        allowed_prefixes = ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
        if not v.startswith(allowed_prefixes):
            raise ValueError(
                "DATABASE_URL must be PostgreSQL (postgresql://...). "
                "SQLite/MySQL/etc are not supported in this project."
            )
        return v
    
    # Environment
    environment: str = "development"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        env = (value or "development").strip().lower()
        if env not in {"development", "staging", "production"}:
            raise ValueError("ENVIRONMENT must be one of: development, staging, production")
        return env

    # Auth
    secret_key: str = os.getenv("SECRET_KEY", "")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        v = (value or "").strip()
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if "your-" in v.lower() or "dev-secret" in v.lower() or "change-this-secret" in v.lower():
            raise ValueError("SECRET_KEY uses a placeholder value. Set a strong unique secret")
        return v

    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours
    refresh_token_expire_days: int = 7
    
    # Email
    mail_username: str = "your@gmail.com"
    mail_password: str = "your-gmail-app-password"
    mail_from: str = "noreply@yourcompany.com"
    mail_port: int = 587
    mail_server: str = "smtp.gmail.com"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False
    
    # Frontend
    frontend_url: str = "http://localhost:3001"

    @field_validator("frontend_url")
    @classmethod
    def validate_frontend_url(cls, value: str) -> str:
        v = (value or "").strip().rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("FRONTEND_URL must start with http:// or https://")
        return v
    
    # Company
    company_name: str = "Your Company Name"

    # Bootstrap admin credentials (used by setup/seed utilities)
    ims_admin_email: str | None = None
    ims_admin_password: str | None = None

    # Rate limiting
    rate_limit_login: str = "5/minute"
    rate_limit_auth: str = "100/minute"
    rate_limit_api: str = "100/minute"

    # CSRF protection (for cookie-auth browser sessions)
    csrf_enabled: bool = True
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = True
    cookie_samesite: str = "strict"

    @field_validator("cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        token = (value or "strict").strip().lower()
        if token not in {"strict", "lax", "none"}:
            raise ValueError("COOKIE_SAMESITE must be one of: strict, lax, none")
        return token

    # Database pooling
    db_pool_size: int = 20
    db_pool_max_overflow: int = 40
    db_pool_recycle_seconds: int = 3600

    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }

    @property
    def csrf_exempt_paths(self) -> list[str]:
        # Login and refresh need to be callable before CSRF token is available.
        return [
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v2/auth/login",
            "/api/v2/auth/refresh",
            "/health",
            "/",
        ]

    @property
    def frontend_allowed_origins(self) -> list[str]:
        raw = (os.getenv("FRONTEND_ALLOWED_ORIGINS") or "").strip()
        if raw:
            origins = [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]
        else:
            origins = [self.frontend_url]

        if self.environment != "production":
            normalized = []
            for origin in origins:
                normalized.append(origin)
                parsed = urlparse(origin)
                host = (parsed.hostname or "").lower()
                if host in {"localhost", "127.0.0.1"} and parsed.scheme and parsed.port:
                    companion_host = "127.0.0.1" if host == "localhost" else "localhost"
                    normalized.append(f"{parsed.scheme}://{companion_host}:{parsed.port}")
            origins = normalized

        return list(dict.fromkeys(origins))


settings = Settings()

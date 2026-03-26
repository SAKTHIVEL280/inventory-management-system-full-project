"""Backend configuration."""
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
    
    # Auth
    secret_key: str = "your-256-bit-secret-key-aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwXyYzZ"
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
    frontend_url: str = "http://localhost:5173"
    
    # Company
    company_name: str = "Your Company Name"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

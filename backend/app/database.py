"""Database configuration and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings


engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "pool_recycle": settings.db_pool_recycle_seconds,
}

if settings.environment == "production":
    engine_kwargs.update(
        {
            "poolclass": QueuePool,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_pool_max_overflow,
        }
    )

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

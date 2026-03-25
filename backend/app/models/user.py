"""User model."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, UUID, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """User model with role-based access control."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default="inventory",
    )
    permission_overrides = Column(JSON, nullable=True, default=None)
    force_password_change = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

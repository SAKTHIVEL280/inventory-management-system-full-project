"""User model."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, UUID, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """User model with role-based access control."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name = Column(String(150), nullable=False)
    # Email is globally unique among ACTIVE users only (partial unique index
    # ux_users_email_active WHERE is_deleted=false), so a deleted user's email
    # can be reused. Column-level unique intentionally omitted.
    email = Column(String(255), nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default="basic",
    )
    permission_overrides = Column(JSON, nullable=True, default=None)
    force_password_change = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    # Platform-level Super Admin (Mecandria team). Super Admins have company_id
    # NULL and manage all tenants via the Super Admin portal (M4).
    is_super_admin = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

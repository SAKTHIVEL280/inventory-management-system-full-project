"""Generic customization option model."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, UUID, ForeignKey, UniqueConstraint
from app.database import Base


class CustomizationOption(Base):
    """Configurable option values used by dropdown-like inputs across modules."""

    __tablename__ = "customization_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    module = Column(String(50), nullable=False, index=True)
    field_name = Column(String(50), nullable=False, index=True)
    option_value = Column(String(120), nullable=False)
    display_label = Column(String(150), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("module", "field_name", "option_value", name="uq_customization_option_scope"),
    )

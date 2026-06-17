"""Sales master-data models managed under Customization.

Enhancement 3 (Sales Invoice mandatory fields):
- Stockist master: Stockist Name, Stockist City, Status (Active/Inactive).
- Sales Manager master: Name, Employee ID (optional), Region, Status.

These back the mandatory Stockist Name / Stockist City / Sales Manager Name
fields on the Sales Invoice. They are company-scoped and soft-deletable so
existing invoices that reference a (now inactive) master entry keep working.
"""
from uuid import uuid4
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, UUID, ForeignKey

from app.database import Base


class Stockist(Base):
    """Stockist master entry (distribution channel)."""

    __tablename__ = "stockists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(150), nullable=False, index=True)
    city = Column(String(120), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class SalesManager(Base):
    """Sales Manager master entry."""

    __tablename__ = "sales_managers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(150), nullable=False, index=True)
    employee_id = Column(String(50), nullable=True)
    region = Column(String(120), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

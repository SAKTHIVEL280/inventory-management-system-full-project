"""Inventory count models for Stock Master enhancements (STO-006/007)."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, UUID, ForeignKey, Numeric, Text

from app.database import Base


class InventoryCount(Base):
    __tablename__ = "inventory_counts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    count_number = Column(String(30), unique=True, nullable=False)
    count_date = Column(Date, nullable=False)
    count_performed_by = Column(String(150), nullable=False)
    status = Column(String(20), nullable=False, default="confirmed")
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class InventoryCountItem(Base):
    __tablename__ = "inventory_count_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    inventory_count_id = Column(UUID(as_uuid=True), ForeignKey("inventory_counts.id"), nullable=False)
    serial_number = Column(Integer, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    product_description = Column(Text, nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    batch_no = Column(String(100), nullable=True)
    manufacture_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class InventoryCountDifferenceAudit(Base):
    __tablename__ = "inventory_count_difference_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    inventory_count_id = Column(UUID(as_uuid=True), ForeignKey("inventory_counts.id"), nullable=False)
    inventory_count_item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_count_items.id"), nullable=False)
    count_number = Column(String(30), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    old_qty = Column(Numeric(12, 4), nullable=False)
    new_qty = Column(Numeric(12, 4), nullable=False)
    difference_qty = Column(Numeric(12, 4), nullable=False)
    reason_code = Column(String(50), nullable=False)
    reason_label = Column(String(120), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    accepted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    accepted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

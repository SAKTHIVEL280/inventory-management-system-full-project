"""Product-related models."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, UUID, ForeignKey, Numeric, Date, Text
from app.database import Base


class ProductCategory(Base):
    """Product category master."""

    __tablename__ = "product_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(150), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class UnitOfMeasure(Base):
    """Units of measure."""

    __tablename__ = "units_of_measure"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(50), nullable=False)
    abbreviation = Column(String(10), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Product(Base):
    """Product master."""

    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_code = Column(String(30), unique=True, nullable=False, index=True)
    sku = Column(String(50), unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    uom_id = Column(UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False)
    alt_uom_id = Column(UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True)
    alt_uom_conversion = Column(Numeric(10, 4), nullable=True)
    hsn_code = Column(String(10), nullable=False)
    gst_rate = Column(Integer, nullable=False)
    purchase_price = Column(Integer, nullable=False, default=0)
    selling_price = Column(Integer, nullable=False, default=0)
    mrp = Column(Integer, nullable=False, default=0)
    minimum_stock = Column(Integer, nullable=False, default=0)
    opening_stock = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class StockLedger(Base):
    """Stock transactions."""

    __tablename__ = "stock_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)
    reference_type = Column(String(20), nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    reference_number = Column(String(50), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    rate = Column(Integer, nullable=False)
    transaction_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

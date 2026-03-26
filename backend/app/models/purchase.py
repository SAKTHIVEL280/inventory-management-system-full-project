"""Purchase workflow models."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, UUID, ForeignKey, Numeric, Text
from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    po_number = Column(String(30), unique=True, nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    subtotal = Column(Integer, nullable=False, default=0)
    total_discount = Column(Integer, nullable=False, default=0)
    total_taxable_amount = Column(Integer, nullable=False, default=0)
    total_cgst = Column(Integer, nullable=False, default=0)
    total_sgst = Column(Integer, nullable=False, default=0)
    total_igst = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    description = Column(String(255), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    unit_price = Column(Integer, nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    taxable_amount = Column(Integer, nullable=False)
    gst_rate = Column(Integer, nullable=False)
    cgst_amount = Column(Integer, nullable=False, default=0)
    sgst_amount = Column(Integer, nullable=False, default=0)
    igst_amount = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False)
    received_quantity = Column(Numeric(12, 4), nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class GoodsReceiptNote(Base):
    __tablename__ = "goods_receipt_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    grn_number = Column(String(30), unique=True, nullable=False)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    supplier_invoice_number = Column(String(50), nullable=True)
    supplier_invoice_date = Column(Date, nullable=True)
    receipt_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    subtotal = Column(Integer, nullable=False, default=0)
    total_discount = Column(Integer, nullable=False, default=0)
    total_taxable_amount = Column(Integer, nullable=False, default=0)
    total_cgst = Column(Integer, nullable=False, default=0)
    total_sgst = Column(Integer, nullable=False, default=0)
    total_igst = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class GRNItem(Base):
    __tablename__ = "grn_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    grn_id = Column(UUID(as_uuid=True), ForeignKey("goods_receipt_notes.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    purchase_order_item_id = Column(UUID(as_uuid=True), ForeignKey("purchase_order_items.id"), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    unit_price = Column(Integer, nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    taxable_amount = Column(Integer, nullable=False)
    gst_rate = Column(Integer, nullable=False)
    cgst_amount = Column(Integer, nullable=False, default=0)
    sgst_amount = Column(Integer, nullable=False, default=0)
    igst_amount = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    return_number = Column(String(30), unique=True, nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    grn_id = Column(UUID(as_uuid=True), ForeignKey("goods_receipt_notes.id"), nullable=False)
    return_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    subtotal = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class PurchaseReturnItem(Base):
    __tablename__ = "purchase_return_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_return_id = Column(UUID(as_uuid=True), ForeignKey("purchase_returns.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    grn_item_id = Column(UUID(as_uuid=True), ForeignKey("grn_items.id"), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    unit_price = Column(Integer, nullable=False)
    taxable_amount = Column(Integer, nullable=False)
    gst_rate = Column(Integer, nullable=False)
    cgst_amount = Column(Integer, nullable=False, default=0)
    sgst_amount = Column(Integer, nullable=False, default=0)
    igst_amount = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

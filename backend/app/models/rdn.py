"""Return Delivery Note (RDN) models."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, UUID, ForeignKey, Numeric, Text
from app.database import Base


class ReturnDeliveryNote(Base):
    __tablename__ = "return_delivery_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    rdn_number = Column(String(30), unique=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    sales_invoice_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=False)
    customer_delivery_number = Column(String(50), nullable=True)
    customer_delivery_date = Column(Date, nullable=False)
    receipt_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)


class ReturnDeliveryNoteItem(Base):
    __tablename__ = "return_delivery_note_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    rdn_id = Column(UUID(as_uuid=True), ForeignKey("return_delivery_notes.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    invoice_item_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoice_items.id"), nullable=True)
    batch_no = Column(String(100), nullable=False)
    manufacture_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    invoice_quantity = Column(Numeric(12, 4), nullable=False)
    return_quantity = Column(Numeric(12, 4), nullable=False)
    mrp = Column(Integer, nullable=True)
    reason_code = Column(String(120), nullable=False)
    reason_label = Column(String(150), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class RdnCreditNote(Base):
    __tablename__ = "rdn_credit_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    credit_note_number = Column(String(30), unique=True, nullable=False)
    rdn_id = Column(UUID(as_uuid=True), ForeignKey("return_delivery_notes.id"), nullable=False)
    sales_invoice_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    credit_note_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="posted")
    subtotal = Column(Integer, nullable=False, default=0)
    total_discount = Column(Integer, nullable=False, default=0)
    total_taxable_amount = Column(Integer, nullable=False, default=0)
    total_cgst = Column(Integer, nullable=False, default=0)
    total_sgst = Column(Integer, nullable=False, default=0)
    total_igst = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class RdnCreditNoteItem(Base):
    __tablename__ = "rdn_credit_note_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    credit_note_id = Column(UUID(as_uuid=True), ForeignKey("rdn_credit_notes.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    invoice_item_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoice_items.id"), nullable=True)
    return_quantity = Column(Numeric(12, 4), nullable=False)
    unit_price = Column(Integer, nullable=False)
    mrp = Column(Integer, nullable=True)
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

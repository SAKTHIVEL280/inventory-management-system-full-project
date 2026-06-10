"""Proforma Invoice models.

Independent replica of the Quotation module (app/models/sales.py:Quotation),
with its own tables and PFI-prefixed numbering. Does not touch Quotation.
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, UUID, ForeignKey, Numeric, Text
from app.database import Base


class ProformaInvoice(Base):
    __tablename__ = "proforma_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    proforma_number = Column(String(30), unique=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    proforma_date = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    sold_to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    bill_to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    ship_to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    subtotal = Column(Integer, nullable=False, default=0)
    total_discount = Column(Integer, nullable=False, default=0)
    total_taxable_amount = Column(Integer, nullable=False, default=0)
    total_cgst = Column(Integer, nullable=False, default=0)
    total_sgst = Column(Integer, nullable=False, default=0)
    total_igst = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    terms_conditions = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ProformaInvoiceItem(Base):
    __tablename__ = "proforma_invoice_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    proforma_invoice_id = Column(UUID(as_uuid=True), ForeignKey("proforma_invoices.id"), nullable=False)
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
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

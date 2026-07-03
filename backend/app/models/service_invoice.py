"""Service Invoice models (Module M5).

GST-compliant service invoices, available to ALL subscription plans (BRD §8).
FREE tier is capped at 10 invoices/calendar month (enforced in the router).
Money is stored as INTEGER (consistent with the rest of the schema); quantities
as NUMERIC. Numbers are per-tenant (composite unique on company_id+number).
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Numeric, Text, UUID, ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database import Base


class ServiceInvoice(Base):
    __tablename__ = "service_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_number = Column(String(40), nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)

    # Customer details (free-form on the service invoice; not the customer master)
    customer_name = Column(String(255), nullable=False)
    customer_gstin = Column(String(15), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_contact = Column(String(20), nullable=True)
    billing_address = Column(Text, nullable=True)
    customer_state_code = Column(String(5), nullable=True)

    # 'intra' (CGST+SGST) | 'inter' (IGST)
    supply_type = Column(String(10), nullable=False, default="intra")

    # Totals (INTEGER)
    subtotal = Column(Integer, nullable=False, default=0)
    total_discount = Column(Integer, nullable=False, default=0)
    total_taxable_amount = Column(Integer, nullable=False, default=0)
    total_cgst = Column(Integer, nullable=False, default=0)
    total_sgst = Column(Integer, nullable=False, default=0)
    total_igst = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    grand_total = Column(Integer, nullable=False, default=0)
    amount_in_words = Column(String(500), nullable=True)

    status = Column(String(20), nullable=False, default="draft")  # draft|issued|paid|cancelled
    payment_status = Column(String(20), nullable=False, default="unpaid")  # unpaid|paid
    cancel_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    # Mecandria's subscription invoice raised BY the Super Admin TO this tenant
    # (BRD §4.3). company_id = the billed tenant. Kept out of the tenant's own
    # service-invoice list and FREE cap; counted as platform subscription revenue.
    is_platform_invoice = Column(Boolean, nullable=False, default=False, index=True)

    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    items = relationship(
        "ServiceInvoiceItem", back_populates="invoice",
        cascade="all, delete-orphan", lazy="selectin",
    )


class ServiceInvoiceItem(Base):
    __tablename__ = "service_invoice_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    service_invoice_id = Column(
        UUID(as_uuid=True), ForeignKey("service_invoices.id", ondelete="CASCADE"), nullable=False,
    )
    sr_no = Column(Integer, nullable=False, default=1)
    item_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    hsn_sac_code = Column(String(20), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False, default=1)
    basic_price = Column(Integer, nullable=False, default=0)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)
    is_free = Column(Boolean, nullable=False, default=False)
    taxable_amount = Column(Integer, nullable=False, default=0)
    gst_rate = Column(Integer, nullable=False, default=18)
    cgst_amount = Column(Integer, nullable=False, default=0)
    sgst_amount = Column(Integer, nullable=False, default=0)
    igst_amount = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)

    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    invoice = relationship("ServiceInvoice", back_populates="items")

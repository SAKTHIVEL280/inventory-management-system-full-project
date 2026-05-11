"""Payment workflow models."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, UUID, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_number = Column(String(30), unique=True, nullable=False)
    payment_type = Column(String(10), nullable=False)  # receipt | payment
    party_type = Column(String(10), nullable=False)    # customer | supplier
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    payment_date = Column(Date, nullable=False)
    amount = Column(Integer, nullable=False)
    payment_mode = Column(String(20), nullable=False)
    reference_number = Column(String(100), nullable=True)
    cheque_date = Column(Date, nullable=True)
    bank_name = Column(String(150), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    allocations = relationship("PaymentAllocation", back_populates="payment")


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=True)
    purchase_grn_id = Column(UUID(as_uuid=True), ForeignKey("goods_receipt_notes.id"), nullable=True)
    allocated_amount = Column(Integer, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    payment = relationship("Payment", back_populates="allocations")
    invoice = relationship("SalesInvoice", primaryjoin="PaymentAllocation.invoice_id == SalesInvoice.id")
    grn = relationship("GoodsReceiptNote", primaryjoin="PaymentAllocation.purchase_grn_id == GoodsReceiptNote.id")

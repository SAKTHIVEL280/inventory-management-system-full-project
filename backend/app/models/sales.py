"""Sales workflow models."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, UUID, ForeignKey, Numeric, Text
from app.database import Base


class Quotation(Base):
    __tablename__ = "quotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    quotation_number = Column(String(30), unique=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    quotation_date = Column(Date, nullable=False)
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
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=False)
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
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    so_number = Column(String(30), unique=True, nullable=False)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
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
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sales_order_id = Column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=False)
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
    fulfilled_quantity = Column(Numeric(12, 4), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_number = Column(String(30), unique=True, nullable=False)
    sales_order_id = Column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    sold_to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    bill_to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    ship_to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    supply_state = Column(String(100), nullable=True)
    supply_state_code = Column(String(5), nullable=True)
    is_igst = Column(Boolean, nullable=False, default=False)
    subtotal = Column(Integer, nullable=False, default=0)
    total_discount = Column(Integer, nullable=False, default=0)
    total_taxable_amount = Column(Integer, nullable=False, default=0)
    total_cgst = Column(Integer, nullable=False, default=0)
    total_sgst = Column(Integer, nullable=False, default=0)
    total_igst = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    amount_paid = Column(Integer, nullable=False, default=0)
    amount_due = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    terms_conditions = Column(Text, nullable=True)
    pdf_url = Column(String(500), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class SalesInvoiceItem(Base):
    __tablename__ = "sales_invoice_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    description = Column(String(255), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
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
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class SalesReturn(Base):
    __tablename__ = "sales_returns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    return_number = Column(String(30), unique=True, nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    return_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    subtotal = Column(Integer, nullable=False, default=0)
    total_gst = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class SalesReturnItem(Base):
    __tablename__ = "sales_return_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sales_return_id = Column(UUID(as_uuid=True), ForeignKey("sales_returns.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    invoice_item_id = Column(UUID(as_uuid=True), ForeignKey("sales_invoice_items.id"), nullable=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    unit_price = Column(Integer, nullable=False)
    taxable_amount = Column(Integer, nullable=False)
    gst_rate = Column(Integer, nullable=False)
    cgst_amount = Column(Integer, nullable=False, default=0)
    sgst_amount = Column(Integer, nullable=False, default=0)
    igst_amount = Column(Integer, nullable=False, default=0)
    total_amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

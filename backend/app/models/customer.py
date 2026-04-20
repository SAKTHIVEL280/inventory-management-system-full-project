"""Customer model."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, UUID, ForeignKey
from app.database import Base
from app.services.encryption import EncryptedString


class Customer(Base):
    """Customer master."""

    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_code = Column(String(20), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    contact_person = Column(String(150), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=False)
    alternate_phone = Column(String(20), nullable=True)
    gstin = Column(String(15), nullable=True, index=True)
    gstin_status = Column(String(20), nullable=False, default="non-registered")
    pan = Column(EncryptedString(255), nullable=True)
    customer_type = Column(String(20), nullable=False, default="regular")
    business_type = Column(String(20), nullable=False, default="domestic")
    company_director_name = Column(String(255), nullable=True)
    company_director_contact = Column(String(255), nullable=True)

    billing_address_line1 = Column(String(255), nullable=True)
    billing_address_line2 = Column(String(255), nullable=True)
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(100), nullable=True)
    billing_state_code = Column(String(5), nullable=True)
    billing_country = Column(String(100), nullable=True)
    billing_pincode = Column(String(10), nullable=True)

    shipping_address_line1 = Column(String(255), nullable=True)
    shipping_address_line2 = Column(String(255), nullable=True)
    shipping_city = Column(String(100), nullable=True)
    shipping_state = Column(String(100), nullable=True)
    shipping_state_code = Column(String(5), nullable=True)
    shipping_country = Column(String(100), nullable=True)
    shipping_pincode = Column(String(10), nullable=True)
    same_as_billing = Column(Boolean, nullable=False, default=True)

    credit_limit = Column(Integer, nullable=False, default=0)
    payment_terms_days = Column(Integer, nullable=True, default=None)
    opening_balance_type = Column(String(2), nullable=False, default="dr")
    currency_code = Column(String(10), nullable=False, default="INR")

    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

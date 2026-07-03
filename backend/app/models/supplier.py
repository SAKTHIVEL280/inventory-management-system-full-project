"""Supplier model."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, UUID, ForeignKey, UniqueConstraint
from app.database import Base
from app.services.encryption import EncryptedString


class Supplier(Base):
    """Supplier master."""

    __tablename__ = "suppliers"
    # supplier_code is unique PER TENANT (multi-tenant); see ux_suppliers_company_code.
    __table_args__ = (UniqueConstraint("company_id", "supplier_code", name="ux_suppliers_company_code"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_code = Column(String(20), nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    contact_person = Column(String(150), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(15), nullable=False)
    alternate_phone = Column(String(15), nullable=True)
    gstin_status = Column(String(20), nullable=False, default="non-registered")
    gstin = Column(String(15), nullable=True, index=True)
    pan = Column(EncryptedString(255), nullable=True)
    business_type = Column(String(20), nullable=False, default="domestic")
    company_director_name = Column(String(255), nullable=True)
    company_director_contact = Column(String(255), nullable=True)

    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    state_code = Column(String(5), nullable=True)
    billing_country = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    place_of_supply = Column(String(255), nullable=True)

    bank_name = Column(String(150), nullable=True)
    bank_account_no = Column(EncryptedString(255), nullable=True)
    bank_ifsc = Column(String(20), nullable=True)

    payment_terms_days = Column(Integer, nullable=False, default=30)
    currency_code = Column(String(10), nullable=False, default="INR")
    opening_balance = Column(Integer, nullable=False, default=0)
    opening_balance_type = Column(String(2), nullable=False, default="cr")

    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

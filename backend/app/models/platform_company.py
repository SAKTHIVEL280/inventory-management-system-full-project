"""Platform (Mecandria) seller company profile.

A single-row table holding the application owner's own company details — used as
the SELLER on Super Admin → tenant subscription service invoices, dashboards, and
any "application seller information". Mirrors the tenant `company` profile columns
so it can be passed to the same PDF helpers. Managed via the Super Admin →
Company Profile page (replaces the env-var seller config).
"""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, DateTime, UUID
from app.database import Base


class PlatformCompany(Base):
    __tablename__ = "platform_company"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    name = Column(String(255), nullable=False, default="Mecandria")
    legal_name = Column(String(255), nullable=True)
    gstin = Column(String(15), nullable=True)
    gstin_status = Column(String(20), nullable=False, default="non-registered")
    pan = Column(String(10), nullable=True)
    import_export_number = Column(String(50), nullable=True)
    company_director_name = Column(String(255), nullable=True)
    company_director_contact = Column(String(255), nullable=True)

    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    state_code = Column(String(5), nullable=True)
    pincode = Column(String(10), nullable=True)

    phone = Column(String(15), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    ambassador_logo_url = Column(String(500), nullable=True)

    bank_name = Column(String(150), nullable=True)
    account_holder_name = Column(String(255), nullable=True)
    bank_account_no = Column(String(50), nullable=True)
    bank_ifsc = Column(String(20), nullable=True)
    bank_branch = Column(String(150), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

"""Company model."""
from uuid import uuid4
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, DateTime, Date, UUID
from app.database import Base


class Company(Base):
    """Tenant registry row: company profile, numbering counters, and (M0+)
    multi-tenant subscription / lifecycle metadata.

    In the shared-database multi-tenant model each row in this table is one
    tenant (ERP Customer). All scoped business tables carry a company_id FK back
    to this row. The legacy single-company deployment is treated as Tenant #1.
    """

    __tablename__ = "company"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    gstin = Column(String(15), unique=True, nullable=True)
    gstin_status = Column(String(20), nullable=False, default='non-registered')
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

    invoice_prefix = Column(String(10), nullable=False, default="INV")
    invoice_counter = Column(Integer, nullable=False, default=1)
    po_prefix = Column(String(10), nullable=False, default="PO")
    po_counter = Column(Integer, nullable=False, default=1)
    so_prefix = Column(String(10), nullable=False, default="SO")
    so_counter = Column(Integer, nullable=False, default=1)
    qtn_prefix = Column(String(10), nullable=False, default="QTN")
    qtn_counter = Column(Integer, nullable=False, default=1)
    pfi_prefix = Column(String(10), nullable=False, default="PFI")
    pfi_counter = Column(Integer, nullable=False, default=1)
    grn_prefix = Column(String(10), nullable=False, default="GRN")
    grn_counter = Column(Integer, nullable=False, default=1)
    rdn_prefix = Column(String(10), nullable=False, default="RDN")
    rdn_counter = Column(Integer, nullable=False, default=1)
    # Service Invoice numbering (M5) — per-tenant sequence.
    svc_prefix = Column(String(10), nullable=False, default="SINV")
    svc_counter = Column(Integer, nullable=False, default=1)

    # ── Multi-tenant registry fields (M0). Additive; no plan gating is enforced
    #    on these yet (that arrives in module M2). The legacy tenant defaults to an
    #    ACTIVE, PLATINUM (full-access), paid account so behaviour is unchanged. ──
    subscription_plan = Column(String(20), nullable=False, default="PLATINUM")
    account_status = Column(String(20), nullable=False, default="active")
    payment_status = Column(String(20), nullable=False, default="paid")
    onboarding_date = Column(Date, nullable=True, default=date.today)
    subscription_start_date = Column(Date, nullable=True)
    subscription_expiry_date = Column(Date, nullable=True)
    business_category = Column(String(100), nullable=True)
    contact_person_name = Column(String(255), nullable=True)
    contact_number = Column(String(20), nullable=True)
    tenant_code = Column(String(50), nullable=True, unique=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

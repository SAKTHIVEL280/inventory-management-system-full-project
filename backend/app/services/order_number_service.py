"""Order number generation service with FOR UPDATE locking.

Fixes BUG-03/04/28: Eliminates race conditions in number generation
by using SELECT ... FOR UPDATE on the company row.

Multi-tenant (M1): every generator accepts an optional ``company_id`` and
locks/increments the counters on *that tenant's* company row, so document
number sequences are independent per tenant. ``company_id=None`` preserves the
legacy single-tenant behaviour (lock the first/only company), keeping older
callers and single-tenant deployments unchanged. The COUNT-based generators are
scoped to the tenant so their sequences are per-tenant as well.
"""
from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.company import Company


def _get_company_locked(db: Session, company_id: Optional[UUID] = None) -> Company:
    """Get and lock the tenant's company row for counter updates.

    With ``company_id`` the row is selected by id (per-tenant numbering). Without
    it, falls back to the first company row (legacy single-tenant behaviour).
    """
    query = db.query(Company).with_for_update()
    if company_id is not None:
        company = query.filter(Company.id == company_id).first()
        if company:
            return company
        # Fall through to legacy behaviour if the id wasn't found (defensive).
    company = db.query(Company).with_for_update().first()
    if not company:
        company = Company(name="My Company")
        db.add(company)
        db.flush()
        company = db.query(Company).with_for_update().first()
    return company


def generate_po_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next purchase order number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    number = f"{company.po_prefix}-{str(company.po_counter).zfill(5)}"
    company.po_counter += 1
    return number


def generate_grn_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next GRN number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    number = f"{company.grn_prefix}-{str(company.grn_counter).zfill(5)}"
    company.grn_counter += 1
    return number


def generate_quotation_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next quotation number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    number = f"{company.qtn_prefix}-{str(company.qtn_counter).zfill(5)}"
    company.qtn_counter += 1
    return number


def generate_proforma_invoice_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next proforma invoice number (thread-safe, per-tenant). e.g. PFI-00001."""
    company = _get_company_locked(db, company_id)
    number = f"{company.pfi_prefix}-{str(company.pfi_counter).zfill(5)}"
    company.pfi_counter += 1
    return number


def generate_so_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next sales order number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    number = f"{company.so_prefix}-{str(company.so_counter).zfill(5)}"
    company.so_counter += 1
    return number


def generate_invoice_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next invoice number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    number = f"{company.invoice_prefix}-{str(company.invoice_counter).zfill(5)}"
    company.invoice_counter += 1
    return number


def generate_rdn_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next RDN number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    number = f"{company.rdn_prefix}-{str(company.rdn_counter).zfill(5)}"
    company.rdn_counter += 1
    return number


def generate_service_invoice_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next service invoice number (thread-safe, per-tenant)."""
    company = _get_company_locked(db, company_id)
    prefix = getattr(company, "svc_prefix", None) or "SINV"
    counter = getattr(company, "svc_counter", None) or 1
    number = f"{prefix}-{str(counter).zfill(5)}"
    company.svc_counter = counter + 1
    return number


def _scoped_count_plus_one(db: Session, table: str, company_id: Optional[UUID]) -> int:
    """COUNT(*)+1 over a table, scoped to the tenant when company_id is given.

    Used by the COUNT-based number sequences. Scoping keeps each tenant's
    sequence independent; without company_id it counts the whole table (legacy).
    """
    if company_id is not None:
        result = db.execute(
            text(f"SELECT COUNT(*) + 1 FROM {table} WHERE company_id = :cid"),
            {"cid": str(company_id)},
        ).scalar()
    else:
        result = db.execute(text(f"SELECT COUNT(*) + 1 FROM {table}")).scalar()
    return int(result or 1)


def generate_purchase_return_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next purchase return number (per-tenant COUNT-based sequence)."""
    n = _scoped_count_plus_one(db, "purchase_returns", company_id)
    return f"PR-{str(n).zfill(5)}"


def generate_sales_return_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next sales return number (per-tenant COUNT-based sequence)."""
    n = _scoped_count_plus_one(db, "sales_returns", company_id)
    return f"SR-{str(n).zfill(5)}"


def generate_payment_number(db: Session, company_id: Optional[UUID] = None) -> str:
    """Generate next payment number (per-tenant COUNT-based sequence)."""
    n = _scoped_count_plus_one(db, "payments", company_id)
    return f"PAY-{str(n).zfill(5)}"

"""Compliance and data-governance endpoints (GDPR/retention support)."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.product import Product
from app.models.purchase import GoodsReceiptNote, PurchaseOrder
from app.models.sales import Quotation, SalesInvoice
from app.models.supplier import Supplier
from app.models.user import User
from app.services.audit_service import log_audit_event


router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity} not found")


@router.get("/export/customer/{customer_id}")
async def export_customer_data(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "accounting")),
):
    """Export customer data bundle for Data Subject Access Request workflows."""
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise _not_found("Customer")

    invoices = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.customer_id == customer_id, SalesInvoice.is_deleted == False)
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer_id, Payment.is_deleted == False)
        .all()
    )

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "customer": jsonable_encoder(customer),
        "sales_invoices": jsonable_encoder(invoices),
        "payments": jsonable_encoder(payments),
    }

    log_audit_event(
        db,
        action="EXPORT_CUSTOMER_DATA",
        resource_type="compliance",
        resource_id=customer_id,
        status="success",
        user_id=current_user.id,
        details={"customer_id": str(customer_id)},
    )
    db.commit()
    return payload


@router.get("/export/supplier/{supplier_id}")
async def export_supplier_data(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "accounting")),
):
    """Export supplier data bundle for legal/compliance requests."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise _not_found("Supplier")

    purchase_orders = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.supplier_id == supplier_id, PurchaseOrder.is_deleted == False)
        .all()
    )
    grns = (
        db.query(GoodsReceiptNote)
        .filter(GoodsReceiptNote.supplier_id == supplier_id, GoodsReceiptNote.is_deleted == False)
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.supplier_id == supplier_id, Payment.is_deleted == False)
        .all()
    )

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "supplier": jsonable_encoder(supplier),
        "purchase_orders": jsonable_encoder(purchase_orders),
        "goods_receipt_notes": jsonable_encoder(grns),
        "payments": jsonable_encoder(payments),
    }

    log_audit_event(
        db,
        action="EXPORT_SUPPLIER_DATA",
        resource_type="compliance",
        resource_id=supplier_id,
        status="success",
        user_id=current_user.id,
        details={"supplier_id": str(supplier_id)},
    )
    db.commit()
    return payload


@router.post("/anonymize/customer/{customer_id}")
async def anonymize_customer_data(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Anonymize customer PII while preserving transactional integrity."""
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise _not_found("Customer")

    suffix = str(customer.id).replace("-", "")[:8]
    customer.company_name = f"Anonymized Customer {suffix}"
    customer.contact_person = None
    customer.email = None
    customer.phone = f"0000{suffix[:6]}"
    customer.alternate_phone = None
    customer.gstin = None
    customer.pan = None
    customer.company_director_name = None
    customer.company_director_contact = None
    customer.billing_address_line1 = None
    customer.billing_address_line2 = None
    customer.billing_city = None
    customer.billing_pincode = None
    customer.shipping_address_line1 = None
    customer.shipping_address_line2 = None
    customer.shipping_city = None
    customer.shipping_pincode = None
    customer.is_active = False

    log_audit_event(
        db,
        action="ANONYMIZE_CUSTOMER",
        resource_type="compliance",
        resource_id=customer_id,
        status="success",
        user_id=current_user.id,
        details={"customer_id": str(customer_id)},
    )
    db.commit()
    return {"message": "Customer personal data anonymized"}


@router.post("/anonymize/supplier/{supplier_id}")
async def anonymize_supplier_data(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Anonymize supplier PII while preserving transactional integrity."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise _not_found("Supplier")

    suffix = str(supplier.id).replace("-", "")[:8]
    supplier.company_name = f"Anonymized Supplier {suffix}"
    supplier.contact_person = None
    supplier.email = None
    supplier.phone = f"0000{suffix[:6]}"
    supplier.alternate_phone = None
    supplier.gstin = None
    supplier.pan = None
    supplier.company_director_name = None
    supplier.company_director_contact = None
    supplier.address_line1 = None
    supplier.address_line2 = None
    supplier.city = None
    supplier.pincode = None
    supplier.bank_name = None
    supplier.bank_account_no = None
    supplier.bank_ifsc = None
    supplier.is_active = False

    log_audit_event(
        db,
        action="ANONYMIZE_SUPPLIER",
        resource_type="compliance",
        resource_id=supplier_id,
        status="success",
        user_id=current_user.id,
        details={"supplier_id": str(supplier_id)},
    )
    db.commit()
    return {"message": "Supplier personal data anonymized"}


@router.get("/retention/summary")
async def retention_summary(
    older_than_days: int = Query(default=365, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "accounting")),
):
    """Show archival candidates older than configured retention window."""
    threshold = datetime.utcnow() - timedelta(days=older_than_days)

    payload = {
        "older_than_days": older_than_days,
        "threshold_utc": threshold.isoformat(),
        "archived_candidates": {
            "customers": db.query(Customer).filter(Customer.is_deleted == True, Customer.deleted_at <= threshold).count(),
            "suppliers": db.query(Supplier).filter(Supplier.is_deleted == True, Supplier.deleted_at <= threshold).count(),
            "products": db.query(Product).filter(Product.is_deleted == True, Product.deleted_at <= threshold).count(),
            "purchase_orders": db.query(PurchaseOrder).filter(PurchaseOrder.is_deleted == True, PurchaseOrder.deleted_at <= threshold).count(),
            "goods_receipt_notes": db.query(GoodsReceiptNote).filter(GoodsReceiptNote.is_deleted == True, GoodsReceiptNote.deleted_at <= threshold).count(),
            "quotations": db.query(Quotation).filter(Quotation.is_deleted == True, Quotation.deleted_at <= threshold).count(),
            "sales_invoices": db.query(SalesInvoice).filter(SalesInvoice.is_deleted == True, SalesInvoice.deleted_at <= threshold).count(),
            "payments": db.query(Payment).filter(Payment.is_deleted == True, Payment.deleted_at <= threshold).count(),
        },
    }

    return payload

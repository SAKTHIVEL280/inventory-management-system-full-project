"""Payments workflow router."""
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.user import User
from app.models.company import Company
from app.models.payment import Payment, PaymentAllocation
from app.models.sales import SalesInvoice
from app.models.purchase import GoodsReceiptNote
from app.schemas.payment import PaymentCreateRequest, PaymentStatusRequest

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def _payment_number(db: Session) -> str:
    count = db.query(Payment).count()
    return f"PAY-{str(count + 1).zfill(5)}"


def _apply_invoice_allocation(db: Session, invoice_id: UUID, amount: int) -> None:
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=400, detail="Invalid invoice allocation")
    if invoice.amount_due <= 0:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    if amount > invoice.amount_due:
        raise HTTPException(status_code=400, detail="Allocated amount exceeds invoice due")

    invoice.amount_paid += amount
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)
    if invoice.amount_due == 0:
        invoice.status = "paid"
    elif invoice.amount_paid > 0:
        invoice.status = "partial_paid"
    else:
        invoice.status = "issued"


def _reverse_invoice_allocation(db: Session, invoice_id: UUID, amount: int) -> None:
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        return
    invoice.amount_paid = max(0, invoice.amount_paid - amount)
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)
    if invoice.amount_paid == 0:
        invoice.status = "issued"
    elif invoice.amount_due == 0:
        invoice.status = "paid"
    else:
        invoice.status = "partial_paid"


@router.get("")
async def list_payments(
    party_type: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_read", "receipts_read")),
):
    query = db.query(Payment).filter(Payment.is_deleted == False)
    if party_type:
        query = query.filter(Payment.party_type == party_type)
    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)
    if supplier_id:
        query = query.filter(Payment.supplier_id == supplier_id)
    if status:
        query = query.filter(Payment.status == status)

    total = query.count()
    items = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("")
async def create_payment(
    payload: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_write", "receipts_write")),
):
    total_allocated = sum(a.allocated_amount for a in payload.allocations)
    if total_allocated > payload.amount:
        raise HTTPException(status_code=400, detail="Total allocations exceed payment amount")

    if payload.party_type == "customer" and not payload.customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required for customer payments")
    if payload.party_type == "supplier" and not payload.supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id is required for supplier payments")

    payment = Payment(
        payment_number=_payment_number(db),
        payment_type=payload.payment_type,
        party_type=payload.party_type,
        customer_id=payload.customer_id,
        supplier_id=payload.supplier_id,
        payment_date=payload.payment_date,
        amount=payload.amount,
        payment_mode=payload.payment_mode,
        reference_number=payload.reference_number,
        cheque_date=payload.cheque_date,
        bank_name=payload.bank_name,
        notes=payload.notes,
        status="pending",
        created_by=current_user.id,
    )
    db.add(payment)
    db.flush()

    for allocation in payload.allocations:
        db.add(PaymentAllocation(
            payment_id=payment.id,
            invoice_id=allocation.invoice_id,
            purchase_grn_id=allocation.purchase_grn_id,
            allocated_amount=allocation.allocated_amount,
        ))
        if allocation.invoice_id:
            _apply_invoice_allocation(db, allocation.invoice_id, allocation.allocated_amount)

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{payment_id}")
async def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_read", "receipts_read")),
):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == False).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    allocations = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == payment_id).all()
    return {"payment": payment, "allocations": allocations}


@router.patch("/{payment_id}/status")
async def update_payment_status(
    payment_id: UUID,
    payload: PaymentStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_write", "receipts_write")),
):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == False).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == "cleared":
        raise HTTPException(status_code=400, detail="Cleared payments cannot be changed")

    if payload.status not in {"pending", "cleared", "bounced", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid payment status")

    if payload.status in {"bounced", "cancelled"} and payment.status == "pending":
        allocations = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == payment.id).all()
        for allocation in allocations:
            if allocation.invoice_id:
                _reverse_invoice_allocation(db, allocation.invoice_id, allocation.allocated_amount)

    payment.status = payload.status
    db.commit()
    db.refresh(payment)
    return payment

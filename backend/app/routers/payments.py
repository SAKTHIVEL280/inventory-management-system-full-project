"""Payments workflow router.

Production-ready with fixes for:
- BUG-09: Balance calculation filters by payment status
- BUG-15: Supplier GRN allocation tracking implemented
- BUG-03: Thread-safe payment number generation
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.dependencies import enforce_resource_ownership, require_permissions
from app.models.user import User
from app.models.company import Company
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.payment import Payment, PaymentAllocation
from app.models.sales import SalesInvoice
from app.models.purchase import GoodsReceiptNote, PurchaseOrder
from app.schemas.payment import PaymentCreateRequest, PaymentStatusRequest
from app.services.order_number_service import generate_payment_number
from app.utils.input_validation import validate_optional_token

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

PO_ID_META_REGEX = re.compile(r"\[PO_ID:([0-9a-fA-F-]{36})\]")


def _scope_to_owner(query, model, current_user: User):
    if current_user.role in {"admin", "accounts"}:
        return query
    owner_col = getattr(model, "created_by", None)
    if owner_col is None:
        return query
    return query.filter(or_(owner_col == current_user.id, owner_col.is_(None)))


def _enforce_owner(record, current_user: User) -> None:
    enforce_resource_ownership(getattr(record, "created_by", None), current_user)


def _to_minor_units(value) -> int:
    """Normalize monetary value to integer minor units (paise)."""
    if value is None:
        return 0
    try:
        normalized = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return 0
    return int(normalized)


def _extract_po_id_from_notes(notes: str | None) -> UUID | None:
    if not notes:
        return None
    match = PO_ID_META_REGEX.search(notes)
    if not match:
        return None
    try:
        return UUID(match.group(1))
    except ValueError:
        return None


def _attach_po_meta_to_notes(notes: str | None, po_id: UUID | None) -> str | None:
    if not po_id:
        return notes
    token = f"[PO_ID:{po_id}]"
    current = (notes or "").strip()
    if token in current:
        return current
    return f"{token} {current}".strip()


def _is_cleared_like_status(status: str | None) -> bool:
    return (status or "").strip().lower() in {
        "cleared",
        "advance_payment_cleared",
        "advance_cleared",
        "full_payment_cleared",
    }


def _payment_has_grn_allocations(payment: Payment) -> bool:
    return any((a.purchase_grn_id is not None) and (not a.is_deleted) for a in (payment.allocations or []))


def _payment_status_display(status: str | None) -> str:
    token = (status or "").strip().lower()
    mapping = {
        "pending": "Pending",
        "cleared": "Cleared",
        "bounced": "Bounced",
        "cancelled": "Cancelled",
        "advance_payment_cleared": "Advance Payment Cleared",
        "advance_cleared": "Advance Payment Cleared",
        "full_payment_cleared": "Full Payment Cleared",
    }
    return mapping.get(token, status or "-")


def _derive_payment_status_token(db: Session, payment: Payment) -> str:
    """Derive UI status token while keeping DB-persisted status backward compatible."""
    token = (payment.status or "").strip().lower()
    if token != "cleared":
        return token or "-"

    if payment.party_type != "supplier":
        return "cleared"

    has_grn_alloc = _payment_has_grn_allocations(payment)
    po_id_from_notes = _extract_po_id_from_notes(payment.notes)

    # Cleared supplier payment with PO tag and no GRN allocation is an advance clear.
    if not has_grn_alloc and po_id_from_notes:
        return "advance_payment_cleared"

    if has_grn_alloc and payment.supplier_id:
        po_ids: set[UUID] = set()
        impacted_grn_ids: set[UUID] = set()

        for allocation in payment.allocations or []:
            if allocation.is_deleted or not allocation.purchase_grn_id:
                continue
            grn = allocation.grn or db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == allocation.purchase_grn_id).first()
            if not grn or not grn.purchase_order_id:
                continue
            po_ids.add(grn.purchase_order_id)
            impacted_grn_ids.add(grn.id)

        if po_ids and impacted_grn_ids:
            snapshot = _build_supplier_payable_snapshot(db, payment.supplier_id, po_ids)
            remaining_by_grn = snapshot["remaining_by_grn"]
            all_fully_paid = all(int(remaining_by_grn.get(grn_id, 0)) == 0 for grn_id in impacted_grn_ids)
            if all_fully_paid:
                return "full_payment_cleared"

    return "cleared"


def _build_supplier_payable_snapshot(
    db: Session,
    supplier_id: UUID,
    po_ids: set[UUID],
    include_payment: Payment | None = None,
) -> dict[str, dict[UUID, int]]:
    """Build PO/GRN payable snapshot with advance and cleared allocations.

    Returns:
    - advance_by_po: cleared advance amount per PO
    - direct_paid_by_grn: cleared paid amount per GRN
    - remaining_by_grn: computed remaining payable per GRN after advance deduction
    - po_for_grn: PO id mapping for GRNs
    """
    advance_by_po: dict[UUID, int] = defaultdict(int)
    direct_paid_by_grn: dict[UUID, int] = defaultdict(int)
    po_for_grn: dict[UUID, UUID] = {}

    confirmed_grns = (
        db.query(GoodsReceiptNote)
        .filter(
            GoodsReceiptNote.supplier_id == supplier_id,
            GoodsReceiptNote.status == "confirmed",
            GoodsReceiptNote.is_deleted == False,
            GoodsReceiptNote.purchase_order_id.isnot(None),
            GoodsReceiptNote.purchase_order_id.in_(list(po_ids)) if po_ids else True,
        )
        .all()
    )

    grns_by_po: dict[UUID, list[GoodsReceiptNote]] = defaultdict(list)
    for grn in confirmed_grns:
        if not grn.purchase_order_id:
            continue
        po_for_grn[grn.id] = grn.purchase_order_id
        grns_by_po[grn.purchase_order_id].append(grn)

    supplier_payments = (
        db.query(Payment)
        .filter(
            Payment.party_type == "supplier",
            Payment.supplier_id == supplier_id,
            Payment.is_deleted == False,
        )
        .all()
    )

    if include_payment is not None and all(p.id != include_payment.id for p in supplier_payments):
        supplier_payments.append(include_payment)

    for payment in supplier_payments:
        if not _is_cleared_like_status(payment.status):
            continue

        if not _payment_has_grn_allocations(payment):
            po_id = _extract_po_id_from_notes(payment.notes)
            if po_id and (not po_ids or po_id in po_ids):
                advance_by_po[po_id] += _to_minor_units(payment.amount)
            continue

        for allocation in payment.allocations or []:
            if allocation.is_deleted or not allocation.purchase_grn_id:
                continue
            grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == allocation.purchase_grn_id).first()
            if not grn or not grn.purchase_order_id:
                continue
            if po_ids and grn.purchase_order_id not in po_ids:
                continue
            direct_paid_by_grn[allocation.purchase_grn_id] += _to_minor_units(allocation.allocated_amount)

    remaining_by_grn: dict[UUID, int] = {}
    for po_id, po_grns in grns_by_po.items():
        advance_left = int(advance_by_po.get(po_id, 0))
        sorted_grns = sorted(po_grns, key=lambda g: (g.receipt_date, g.created_at))
        for grn in sorted_grns:
            total = _to_minor_units(grn.total_amount)
            direct_paid = _to_minor_units(direct_paid_by_grn.get(grn.id, 0))
            due_before_advance = max(0, total - direct_paid)
            applied_advance = min(due_before_advance, max(0, advance_left))
            remaining = max(0, due_before_advance - applied_advance)
            advance_left = max(0, advance_left - applied_advance)
            remaining_by_grn[grn.id] = remaining

    return {
        "advance_by_po": advance_by_po,
        "direct_paid_by_grn": direct_paid_by_grn,
        "remaining_by_grn": remaining_by_grn,
        "po_for_grn": po_for_grn,
    }


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


def _get_customer_open_invoices(db: Session, customer_id: UUID) -> list[SalesInvoice]:
    return (
        db.query(SalesInvoice)
        .filter(
            SalesInvoice.customer_id == customer_id,
            SalesInvoice.is_deleted == False,
            SalesInvoice.amount_due > 0,
            SalesInvoice.status.in_(["issued", "partial_paid"]),
        )
        .all()
    )


# BUG-15: Supplier GRN allocation tracking
def _apply_grn_allocation(db: Session, grn_id: UUID, amount: int) -> None:
    """Track payment allocation against a GRN for supplier balance tracking."""
    grn = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.id == grn_id,
        GoodsReceiptNote.is_deleted == False,
    ).first()
    if not grn:
        raise HTTPException(status_code=400, detail="Invalid GRN for allocation")
    # GRN doesn't have amount_paid/amount_due fields natively,
    # but the allocation record tracks it. No-op for now but
    # the allocation is properly saved for balance calculation.


def _reverse_grn_allocation(db: Session, grn_id: UUID, amount: int) -> None:
    """Reverse a GRN allocation (for bounced/cancelled payments)."""
    # Allocation record remains for audit, no GRN fields to update
    pass


@router.get("")
async def list_payments(
    party_type: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_read", "receipts_read")),
):
    party_type = validate_optional_token(
        party_type,
        field_name="party_type",
        allowed={"customer", "supplier"},
    )
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={
            "draft",
            "pending",
            "cleared",
            "bounced",
            "cancelled",
            "advance_payment_cleared",
            "advance_cleared",
            "full_payment_cleared",
        },
    )

    query = db.query(Payment)
    query = _scope_to_owner(query, Payment, current_user)
    if archived_only:
        query = query.filter(Payment.is_deleted == True)
    elif not include_archived:
        query = query.filter(Payment.is_deleted == False)
    if party_type:
        query = query.filter(Payment.party_type == party_type)
    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)
    if supplier_id:
        query = query.filter(Payment.supplier_id == supplier_id)
    derived_status_filter = None
    if status:
        normalized_status = status.strip().lower()
        if normalized_status in {"advance_payment_cleared", "advance_cleared", "full_payment_cleared"}:
            derived_status_filter = "advance_payment_cleared" if normalized_status == "advance_cleared" else normalized_status
            query = query.filter(Payment.status == "cleared")
        elif normalized_status == "cleared":
            query = query.filter(Payment.status == "cleared")
        else:
            query = query.filter(Payment.status == normalized_status)

    if derived_status_filter:
        all_items = query.order_by(Payment.created_at.desc()).all()
        matched = [p for p in all_items if _derive_payment_status_token(db, p) == derived_status_filter]
        total = len(matched)
        start = (page - 1) * page_size
        end = start + page_size
        items = matched[start:end]
    else:
        total = query.count()
        items = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    # Serialize with allocations for frontend display
    items_out = []
    for p in items:
        po_id_from_notes = _extract_po_id_from_notes(p.notes)
        po_number_from_notes = None
        if po_id_from_notes:
            po_row = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id_from_notes).first()
            po_number_from_notes = po_row.po_number if po_row else None

        allocation_po_ids: set[str] = set()
        allocation_po_numbers: set[str] = set()
        allocation_grn_totals: dict[str, int] = {}
        status_token = _derive_payment_status_token(db, p)

        p_dict = {
            "id": str(p.id),
            "payment_number": p.payment_number,
            "payment_type": p.payment_type,
            "party_type": p.party_type,
            "customer_id": str(p.customer_id) if p.customer_id else None,
            "supplier_id": str(p.supplier_id) if p.supplier_id else None,
            "payment_date": str(p.payment_date),
            "amount": p.amount,
            "payment_mode": p.payment_mode,
            "reference_number": p.reference_number,
            "cheque_date": str(p.cheque_date) if p.cheque_date else None,
            "status": status_token,
            "status_display": _payment_status_display(status_token),
            "purchase_order_id": str(po_id_from_notes) if po_id_from_notes else None,
            "po_number": po_number_from_notes,
            "grn_value": None,
            "allocations": []
        }
        for a in p.allocations:
            if a.is_deleted:
                continue
            alloc_dict = {
                "allocated_amount": a.allocated_amount,
            }
            if a.invoice:
                alloc_dict["invoice_number"] = a.invoice.invoice_number
            if a.grn:
                alloc_dict["grn_number"] = a.grn.grn_number
                grn_total_amount = int(a.grn.total_amount or 0)
                alloc_dict["grn_total_amount"] = grn_total_amount
                grn_key = str(a.grn.id)
                allocation_grn_totals[grn_key] = grn_total_amount
                if a.grn.purchase_order_id:
                    po_row = db.query(PurchaseOrder).filter(PurchaseOrder.id == a.grn.purchase_order_id).first()
                    if po_row:
                        alloc_dict["po_number"] = po_row.po_number
                        alloc_dict["purchase_order_id"] = str(po_row.id)
                        allocation_po_ids.add(str(po_row.id))
                        allocation_po_numbers.add(po_row.po_number)
            p_dict["allocations"].append(alloc_dict)

        if not p_dict["purchase_order_id"] and len(allocation_po_ids) == 1:
            p_dict["purchase_order_id"] = next(iter(allocation_po_ids))
        if not p_dict["po_number"] and len(allocation_po_numbers) == 1:
            p_dict["po_number"] = next(iter(allocation_po_numbers))
        if allocation_grn_totals:
            p_dict["grn_value"] = sum(allocation_grn_totals.values())

        items_out.append(p_dict)
        
    return {"items": items_out, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}

@router.post("")
async def create_payment(
    payload: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_write", "receipts_write")),
):
    normalized_payment_amount = _to_minor_units(payload.amount)
    total_allocated = sum(_to_minor_units(a.allocated_amount) for a in payload.allocations)

    if normalized_payment_amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    if total_allocated > normalized_payment_amount:
        raise HTTPException(status_code=400, detail="Total allocations exceed payment amount")

    if payload.party_type == "customer" and not payload.customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required for customer payments")
    if payload.party_type == "supplier" and not payload.supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id is required for supplier payments")

    if payload.party_type == "customer" and payload.customer_id:
        customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
        if not customer:
            raise HTTPException(status_code=400, detail="Invalid customer")
        _enforce_owner(customer, current_user)

        open_invoices = _get_customer_open_invoices(db, payload.customer_id)
        if not open_invoices:
            raise HTTPException(status_code=400, detail="No Open Invoice")
        for invoice in open_invoices:
            _enforce_owner(invoice, current_user)

        open_invoice_ids = {invoice.id for invoice in open_invoices}
        for allocation in payload.allocations:
            if allocation.purchase_grn_id:
                raise HTTPException(status_code=400, detail="GRN allocations are not allowed for customer payments")
            if not allocation.invoice_id:
                raise HTTPException(status_code=400, detail="invoice_id is required for customer payment allocations")
            if allocation.invoice_id not in open_invoice_ids:
                raise HTTPException(
                    status_code=400,
                    detail="Selected invoice is not an open invoice for this customer",
                )

    selected_po = None
    if payload.party_type == "supplier" and payload.purchase_order_id:
        supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="Invalid supplier")
        _enforce_owner(supplier, current_user)

        selected_po = db.query(PurchaseOrder).filter(
            PurchaseOrder.id == payload.purchase_order_id,
            PurchaseOrder.supplier_id == payload.supplier_id,
            PurchaseOrder.is_deleted == False,
        ).first()
        if not selected_po:
            raise HTTPException(status_code=400, detail="Invalid Purchase Order for selected supplier")
        _enforce_owner(selected_po, current_user)

    if payload.party_type == "supplier" and payload.supplier_id and not payload.purchase_order_id:
        supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="Invalid supplier")
        _enforce_owner(supplier, current_user)

    if payload.party_type == "supplier" and not payload.allocations and not payload.purchase_order_id:
        raise HTTPException(status_code=400, detail="PO Number is required for supplier advance payment")

    # Validate supplier GRN allocations with advance-adjusted remaining payable
    if payload.party_type == "supplier" and payload.allocations:
        grn_rows: dict[UUID, GoodsReceiptNote] = {}
        po_ids: set[UUID] = set()
        for allocation in payload.allocations:
            if not allocation.purchase_grn_id:
                continue
            grn = db.query(GoodsReceiptNote).filter(
                GoodsReceiptNote.id == allocation.purchase_grn_id,
                GoodsReceiptNote.is_deleted == False,
                GoodsReceiptNote.status == "confirmed",
            ).first()
            if not grn:
                raise HTTPException(status_code=400, detail="Invalid confirmed GRN allocation")
            _enforce_owner(grn, current_user)
            if payload.supplier_id and grn.supplier_id != payload.supplier_id:
                raise HTTPException(status_code=400, detail="Selected GRN does not belong to supplier")
            if not grn.purchase_order_id:
                raise HTTPException(status_code=400, detail="Selected GRN is not linked to a Purchase Order")
            grn_rows[allocation.purchase_grn_id] = grn
            po_ids.add(grn.purchase_order_id)

        snapshot = _build_supplier_payable_snapshot(db, payload.supplier_id, po_ids)
        remaining_by_grn = snapshot["remaining_by_grn"]

        new_alloc_sum_by_grn: dict[UUID, int] = defaultdict(int)
        for allocation in payload.allocations:
            if not allocation.purchase_grn_id:
                continue
            grn_id = allocation.purchase_grn_id
            proposed = _to_minor_units(allocation.allocated_amount)
            if proposed <= 0:
                continue
            already_new = _to_minor_units(new_alloc_sum_by_grn[grn_id])
            remaining_now = max(0, _to_minor_units(remaining_by_grn.get(grn_id, 0)) - already_new)
            if proposed > remaining_now:
                grn = grn_rows.get(grn_id)
                label = grn.grn_number if grn else str(grn_id)
                raise HTTPException(status_code=400, detail=f"Payment exceeds remaining payable for GRN {label}")
            new_alloc_sum_by_grn[grn_id] += proposed

    # BUG-03: Thread-safe number generation
    payment_number = generate_payment_number(db)

    payment = Payment(
        payment_number=payment_number,
        payment_type=payload.payment_type,
        party_type=payload.party_type,
        customer_id=payload.customer_id,
        supplier_id=payload.supplier_id,
        payment_date=payload.payment_date,
        amount=normalized_payment_amount,
        payment_mode=payload.payment_mode,
        reference_number=payload.reference_number,
        cheque_date=payload.cheque_date,
        bank_name=payload.bank_name,
        notes=_attach_po_meta_to_notes(payload.notes, payload.purchase_order_id),
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
            allocated_amount=_to_minor_units(allocation.allocated_amount),
        ))
        # BUG-15: Handle both invoice and GRN allocations
        if allocation.invoice_id:
            _apply_invoice_allocation(db, allocation.invoice_id, _to_minor_units(allocation.allocated_amount))
        if allocation.purchase_grn_id:
            _apply_grn_allocation(db, allocation.purchase_grn_id, _to_minor_units(allocation.allocated_amount))

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
    _enforce_owner(payment, current_user)
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
    _enforce_owner(payment, current_user)

    if payment.status in {"cleared", "advance_payment_cleared", "advance_cleared", "full_payment_cleared"}:
        raise HTTPException(status_code=400, detail="Cleared payments cannot be changed")

    requested_status = (payload.status or "").strip().lower()
    if requested_status in {"advance_payment_cleared", "advance_cleared", "full_payment_cleared"}:
        requested_status = "cleared"

    if requested_status not in {"pending", "cleared", "bounced", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid payment status")

    # BUG-15: Reverse both invoice AND GRN allocations on bounce/cancel
    if requested_status in {"bounced", "cancelled"} and payment.status == "pending":
        allocations = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == payment.id).all()
        for allocation in allocations:
            if allocation.invoice_id:
                _reverse_invoice_allocation(db, allocation.invoice_id, allocation.allocated_amount)
            if allocation.purchase_grn_id:
                _reverse_grn_allocation(db, allocation.purchase_grn_id, allocation.allocated_amount)

    payment.status = requested_status
    db.commit()
    db.refresh(payment)
    return payment


@router.patch("/{payment_id}/archive")
async def archive_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_write", "receipts_write")),
):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == False).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    _enforce_owner(payment, current_user)

    payment.is_deleted = True
    payment.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(payment)
    return payment


@router.patch("/{payment_id}/restore")
async def restore_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("payments_write", "receipts_write")),
):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_deleted == True).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Archived payment not found")
    _enforce_owner(payment, current_user)

    payment.is_deleted = False
    payment.deleted_at = None
    db.commit()
    db.refresh(payment)
    return payment

"""Purchase workflow router (PO, GRN, Purchase Return).

Production-ready with fixes for:
- BUG-01: Materialized view refresh after stock changes
- BUG-02: IGST auto-detection from state codes 
- BUG-03: FOR UPDATE lock on number generation
- BUG-04: Safe return number generation
- BUG-13: Force draft status on creation
- BUG-16: Cancel return no longer requires body
- BUG-17: Product validation on PO update
- BUG-19: Return tax matches original document
- BUG-22: GRN items validated against PO products
- BUG-24: Guard against already-received POs
"""
from datetime import datetime, date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.dependencies import enforce_resource_ownership, require_permissions, require_role, scope_query_to_company
from app.models.user import User
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.purchase import (
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceiptNote,
    GRNItem,
    PurchaseReturn,
    PurchaseReturnItem,
)
from app.models.payment import Payment, PaymentAllocation
from app.schemas.purchase import (
    PurchaseOrderCreateRequest,
    PurchaseOrderStatusRequest,
    GRNCreateRequest,
    GRNReverseRequest,
    GRNConfirmedEditRequest,
    PurchaseReturnCreateRequest,
)
from app.services.order_number_service import (
    generate_po_number,
    generate_grn_number,
    generate_purchase_return_number,
)
from app.services.gst_service import determine_tax_mode, calc_line_item, split_tax
from app.services.stock_service import add_stock_entry, refresh_materialized_view, get_product_batch_snapshot, get_current_stock
from app.services.audit_service import log_audit_event
from app.services.auth_service import normalize_role
from app.utils.input_validation import validate_optional_token

router = APIRouter(tags=["purchase"])


def _scope_to_owner(query, model, current_user: User):
    """Scope by company_id first, then by ownership for non-privileged users."""
    if current_user.company_id is not None:
        query = scope_query_to_company(query, model, current_user.company_id)
    if normalize_role(current_user.role) in {"admin", "inventory manager", "general manager"}:
        return query
    owner_col = getattr(model, "created_by", None)
    if owner_col is None:
        return query
    return query.filter(or_(owner_col == current_user.id, owner_col.is_(None)))


def _has_text(value: str | None) -> bool:
    return bool((value or "").strip())


def _enforce_supplier_gstin_for_gst_purchase(*, supplier: Supplier, gst_applicable: bool) -> None:
    if not gst_applicable:
        return

    gstin_status = (supplier.gstin_status or "").strip().lower()
    gstin = ((supplier.gstin or "") or "").strip().upper()
    if gstin:
        return

    if gstin_status == "registered":
        raise HTTPException(
            status_code=400,
            detail="Supplier GSTIN is required for GST-reportable purchases",
        )

    errors: list[str] = []
    if not _has_text(supplier.state):
        errors.append("State is required for Non-Registered GST suppliers")
    if not _has_text(supplier.state_code):
        errors.append("State Code is required for GST calculation")
    if errors:
        raise HTTPException(status_code=400, detail=errors)


def _enforce_owner(record, current_user: User) -> None:
    enforce_resource_ownership(getattr(record, "created_by", None), current_user)


def _derive_grn_status_display(raw_status: str | None, is_partial_qty: bool) -> str:
    status = (raw_status or "").strip().lower()
    if status == "draft":
        return "Partial Receipt (Draft)" if is_partial_qty else "Draft"
    if status == "confirmed":
        return "Partial Receipt (Confirmed)" if is_partial_qty else "Confirmed"
    if status == "cancelled":
        return "Cancelled"
    if status == "reversed":
        return "Reversed"
    return (raw_status or "-").strip() or "-"


def _get_partial_qty_grn_ids(db: Session, grn_ids: list[UUID]) -> set[str]:
    if not grn_ids:
        return set()

    rows = (
        db.query(GRNItem.grn_id)
        .join(PurchaseOrderItem, GRNItem.purchase_order_item_id == PurchaseOrderItem.id)
        .filter(
            GRNItem.grn_id.in_(grn_ids),
            GRNItem.is_deleted == False,
            PurchaseOrderItem.is_deleted == False,
            GRNItem.quantity < PurchaseOrderItem.quantity,
        )
        .distinct()
        .all()
    )
    return {str(row.grn_id) for row in rows}


def _validate_under_delivery_tolerance(under_delivery_tolerance: float, order_quantity: float) -> None:
    if order_quantity > 0 and under_delivery_tolerance >= order_quantity:
        raise HTTPException(
            status_code=400,
            detail="Under delivery tolerance must be less than order quantity",
        )


def _validate_payload_under_delivery_tolerance(under_delivery_tolerance: float, items: list) -> None:
    for item in items:
        _validate_under_delivery_tolerance(
            float(under_delivery_tolerance or 0),
            float(getattr(item, "quantity", 0) or 0),
        )


# ────────────────────────────── Purchase Orders ──────────────────────────────

@router.get("/api/v1/purchase-orders")
async def list_purchase_orders(
    status: str | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_read", "payments_read")),
):
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={"draft", "sent", "partial", "received", "completed", "cancelled", "confirmed"},
    )

    query = db.query(PurchaseOrder)
    query = _scope_to_owner(query, PurchaseOrder, current_user)
    if archived_only:
        query = query.filter(PurchaseOrder.is_deleted == True)
    elif not include_archived:
        query = query.filter(PurchaseOrder.is_deleted == False)
    if status:
        normalized_status = status.strip().lower()
        if normalized_status in {"completed", "received"}:
            query = query.filter(PurchaseOrder.status.in_(["completed", "received"]))
        else:
            query = query.filter(PurchaseOrder.status == normalized_status)
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    total = query.count()
    rows = query.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/purchase-orders")
async def create_purchase_order(
    request: Request,
    payload: PurchaseOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")
    _enforce_owner(supplier, current_user)
    _enforce_owner(supplier, current_user)

    # BUG-02: Auto-detect GST mode based on supplier country/state
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]
    _enforce_supplier_gstin_for_gst_purchase(supplier=supplier, gst_applicable=gst_applicable)
    _enforce_supplier_gstin_for_gst_purchase(supplier=supplier, gst_applicable=gst_applicable)

    # BUG-03: Thread-safe number generation with FOR UPDATE lock
    po_number = generate_po_number(db)

    under_delivery_tolerance = float(payload.under_delivery_tolerance or 0)
    _validate_payload_under_delivery_tolerance(under_delivery_tolerance, payload.items)

    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=payload.supplier_id,
        order_date=payload.order_date,
        expected_delivery_date=payload.expected_delivery_date,
        status="draft",  # BUG-13: Always force draft on create
        currency_code=payload.currency_code,
        exchange_rate=payload.exchange_rate,
        under_delivery_tolerance=under_delivery_tolerance,
        over_delivery_tolerance=payload.over_delivery_tolerance,
        notes=payload.notes,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(po)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        row = PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        )
        db.add(row)
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    po.subtotal = subtotal
    po.total_discount = total_discount
    po.total_taxable_amount = total_taxable
    po.total_cgst = total_cgst
    po.total_sgst = total_sgst
    po.total_igst = total_igst
    po.total_gst = total_cgst + total_sgst + total_igst
    po.total_amount = total_taxable + po.total_gst
    db.commit()
    db.refresh(po)
    
    # Log audit event with PO number
    log_audit_event(
        db,
        action=f"POST:/api/v1/purchase-orders",
        resource_type="purchase-orders",
        status="success",
        user_id=current_user.id,
        resource_id=po.id,
        details={
            "po_number": po.po_number,
            "supplier_id": str(po.supplier_id),
            "total_amount": po.total_amount,
            "status": po.status,
            "method": "POST",
            "path": "/api/v1/purchase-orders",
        },
        ip_address=request.client.host if request.client else None,
    )
    
    return po


@router.get("/api/v1/purchase-orders/{po_id}")
async def get_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_read", "payments_read")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    _enforce_owner(po, current_user)
    items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po_id).all()
    return {"purchase_order": po, "items": items}


@router.put("/api/v1/purchase-orders/{po_id}")
async def update_purchase_order(
    po_id: UUID,
    payload: PurchaseOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    _enforce_owner(po, current_user)
    if po.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase orders can be edited")

    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")
    _enforce_owner(supplier, current_user)

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]
    _enforce_supplier_gstin_for_gst_purchase(supplier=supplier, gst_applicable=gst_applicable)

    under_delivery_tolerance = float(payload.under_delivery_tolerance or 0)
    _validate_payload_under_delivery_tolerance(under_delivery_tolerance, payload.items)

    po.supplier_id = payload.supplier_id
    po.order_date = payload.order_date
    po.expected_delivery_date = payload.expected_delivery_date
    po.currency_code = payload.currency_code
    po.exchange_rate = payload.exchange_rate
    po.under_delivery_tolerance = under_delivery_tolerance
    po.over_delivery_tolerance = payload.over_delivery_tolerance
    po.notes = payload.notes

    db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        # BUG-17: Validate products on update too
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    po.subtotal = subtotal
    po.total_discount = total_discount
    po.total_taxable_amount = total_taxable
    po.total_cgst = total_cgst
    po.total_sgst = total_sgst
    po.total_igst = total_igst
    po.total_gst = total_cgst + total_sgst + total_igst
    po.total_amount = total_taxable + po.total_gst
    db.commit()
    db.refresh(po)
    return po


@router.patch("/api/v1/purchase-orders/{po_id}/status")
async def update_purchase_order_status(
    po_id: UUID,
    payload: PurchaseOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    _enforce_owner(po, current_user)

    requested_status = (payload.status or "").strip().lower()
    if requested_status == "received":
        requested_status = "completed"

    current_status = (po.status or "").strip().lower()
    if current_status == "received":
        current_status = "completed"

    allowed = {
        "draft": {"sent", "cancelled"},
        "sent": {"cancelled", "partial", "completed"},
        "partial": {"completed"},
    }
    if requested_status not in allowed.get(current_status, set()):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    if current_status == "draft" and requested_status == "sent":
        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id, Supplier.is_deleted == False).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="Cannot send PO: supplier reference is invalid")
        _enforce_owner(supplier, current_user)

    # Database check constraint currently stores terminal fulfillment as `received`.
    po.status = "received" if requested_status == "completed" else requested_status
    db.commit()
    db.refresh(po)
    return po


@router.patch("/api/v1/purchase-orders/{po_id}/archive")
async def archive_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    _enforce_owner(po, current_user)

    po.is_deleted = True
    po.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(po)
    return po


@router.patch("/api/v1/purchase-orders/{po_id}/restore")
async def restore_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == True).first()
    if not po:
        raise HTTPException(status_code=404, detail="Archived purchase order not found")
    _enforce_owner(po, current_user)

    po.is_deleted = False
    po.deleted_at = None
    db.commit()
    db.refresh(po)
    return po


# ────────────────────────────── Goods Receipt Notes ──────────────────────────

@router.get("/api/v1/grn")
async def list_grn(
    status: str | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_read", "payments_read")),
):
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={"draft", "confirmed", "cancelled"},
    )

    query = db.query(GoodsReceiptNote)
    query = _scope_to_owner(query, GoodsReceiptNote, current_user)
    if archived_only:
        query = query.filter(GoodsReceiptNote.is_deleted == True)
    elif not include_archived:
        query = query.filter(GoodsReceiptNote.is_deleted == False)
    if status:
        query = query.filter(GoodsReceiptNote.status == status)
    if supplier_id:
        query = query.filter(GoodsReceiptNote.supplier_id == supplier_id)
    total = query.count()
    rows = query.order_by(GoodsReceiptNote.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    partial_qty_grn_ids = _get_partial_qty_grn_ids(db, [g.id for g in rows])

    # GRN-003: Resolve PO numbers for linked GRNs
    po_ids = {str(g.purchase_order_id) for g in rows if g.purchase_order_id}
    po_number_map: dict[str, str] = {}
    if po_ids:
        po_rows = db.query(PurchaseOrder.id, PurchaseOrder.po_number).filter(
            PurchaseOrder.id.in_([g.purchase_order_id for g in rows if g.purchase_order_id])
        ).all()
        po_number_map = {str(po.id): po.po_number for po in po_rows}

    items_out = []
    for g in rows:
        g_dict = {
            c.name: getattr(g, c.name)
            for c in g.__table__.columns
        }
        # Convert UUID/date fields for JSON serialization
        for k, v in g_dict.items():
            if hasattr(v, 'hex'):
                g_dict[k] = str(v)
            elif hasattr(v, 'isoformat'):
                g_dict[k] = v.isoformat()
        is_partial_qty = str(g.id) in partial_qty_grn_ids
        g_dict["po_number"] = po_number_map.get(str(g.purchase_order_id)) if g.purchase_order_id else None
        g_dict["is_partial_qty"] = is_partial_qty
        g_dict["status_display"] = _derive_grn_status_display(g.status, is_partial_qty)
        items_out.append(g_dict)

    return {"items": items_out, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/grn")
async def create_grn(
    request: Request,
    payload: GRNCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    # Validate receipt date is not in the future
    from datetime import date
    if payload.receipt_date > date.today():
        raise HTTPException(status_code=400, detail="Receipt date cannot be a future date. Please select today or a past date.")

    # Calculate payment due date: receipt_date + supplier payment_terms_days
    payment_due_date = None
    if payload.receipt_date and supplier.payment_terms_days:
        from datetime import timedelta
        payment_due_date = payload.receipt_date + timedelta(days=supplier.payment_terms_days)

    po = None
    po_product_ids = set()
    po_items_by_id: dict[UUID, PurchaseOrderItem] = {}
    po_items_by_product: dict[UUID, list[PurchaseOrderItem]] = {}
    under_delivery_tolerance = float(payload.under_delivery_tolerance or 0)
    over_delivery_tolerance = float(payload.over_delivery_tolerance or 0)
    if payload.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.is_deleted == False).first()
        if not po:
            raise HTTPException(status_code=400, detail="Invalid purchase order")
        _enforce_owner(po, current_user)
        if po.status not in {"sent", "partial"}:
            raise HTTPException(status_code=400, detail="GRN can be created only from sent or partial purchase orders")
        if po.supplier_id != payload.supplier_id:
            raise HTTPException(status_code=400, detail="Supplier does not match selected purchase order")
        # BUG-22: Collect valid product IDs from the PO
        po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).all()
        po_product_ids = {item.product_id for item in po_items}
        po_items_by_id = {item.id: item for item in po_items}
        for po_item in po_items:
            po_items_by_product.setdefault(po_item.product_id, []).append(po_item)
        under_delivery_tolerance = float(po.under_delivery_tolerance or 0)
        over_delivery_tolerance = float(po.over_delivery_tolerance or 0)

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]
    _enforce_supplier_gstin_for_gst_purchase(supplier=supplier, gst_applicable=gst_applicable)

    grn_number = generate_grn_number(db)
    grn = GoodsReceiptNote(
        grn_number=grn_number,
        purchase_order_id=payload.purchase_order_id,
        supplier_id=payload.supplier_id,
        supplier_invoice_number=payload.supplier_invoice_number,
        supplier_invoice_date=payload.supplier_invoice_date,
        receipt_date=payload.receipt_date,
        payment_due_date=payment_due_date,
        under_delivery_tolerance=under_delivery_tolerance,
        over_delivery_tolerance=over_delivery_tolerance,
        status="draft",
        notes=payload.notes,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(grn)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for idx, item in enumerate(payload.items, start=1):
        resolved_po_item_id = item.purchase_order_item_id

        # Validate product exists
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)

        # GRN-007: MFG date must be a past date only
        from datetime import date
        if item.manufacture_date and item.manufacture_date >= date.today():
            raise HTTPException(
                status_code=400,
                detail="MFG Date must be a past date",
            )

        # GRN-008: Expiry date must be a future date only
        if item.expiry_date and item.expiry_date <= date.today():
            raise HTTPException(
                status_code=400,
                detail=f"Line item {idx}: expiry date must be a future date",
            )

        if item.manufacture_date and item.expiry_date and item.expiry_date < item.manufacture_date:
            raise HTTPException(
                status_code=400,
                detail=f"Line item {idx}: expiry date cannot be earlier than manufacture date",
            )

        # BUG-22: If linked to PO, validate product is in the PO
        if payload.purchase_order_id and po_product_ids and item.product_id not in po_product_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Product {product.name} is not part of the linked purchase order",
            )

        # PUR-006: Validate received quantity using tolerance in quantity units
        if payload.purchase_order_id:
            po_item = None
            if item.purchase_order_item_id:
                po_item = po_items_by_id.get(item.purchase_order_item_id)
            else:
                po_candidates = po_items_by_product.get(item.product_id, [])
                if len(po_candidates) == 1:
                    po_item = po_candidates[0]

            if not po_item:
                raise HTTPException(status_code=400, detail="Unable to map GRN line item to purchase order line item")

            resolved_po_item_id = po_item.id

            ordered_qty = float(po_item.quantity or 0)
            _validate_under_delivery_tolerance(under_delivery_tolerance, ordered_qty)
            previously_received_qty = float(po_item.received_quantity or 0)
            current_receipt_qty = float(item.quantity or 0)
            cumulative_received_qty = previously_received_qty + current_receipt_qty
            minimum_allowed = max(0.0, ordered_qty - under_delivery_tolerance)
            maximum_allowed = ordered_qty + over_delivery_tolerance

            if cumulative_received_qty < minimum_allowed:
                raise HTTPException(status_code=400, detail="Under delivery exceeded allowed tolerance")
            if cumulative_received_qty > maximum_allowed:
                raise HTTPException(status_code=400, detail="Over delivery exceeded allowed tolerance")

        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(GRNItem(
            grn_id=grn.id,
            product_id=item.product_id,
            purchase_order_item_id=resolved_po_item_id,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    grn.subtotal = subtotal
    grn.total_discount = total_discount
    grn.total_taxable_amount = total_taxable
    grn.total_cgst = total_cgst
    grn.total_sgst = total_sgst
    grn.total_igst = total_igst
    grn.total_gst = total_cgst + total_sgst + total_igst
    grn.total_amount = total_taxable + grn.total_gst

    db.commit()
    db.refresh(grn)
    
    # Log audit event with GRN number
    log_audit_event(
        db,
        action=f"POST:/api/v1/grn",
        resource_type="grn",
        status="success",
        user_id=current_user.id,
        resource_id=grn.id,
        details={
            "grn_number": grn.grn_number,
            "supplier_id": str(grn.supplier_id),
            "total_amount": grn.total_amount,
            "status": grn.status,
            "purchase_order_id": str(grn.purchase_order_id) if grn.purchase_order_id else None,
            "method": "POST",
            "path": "/api/v1/grn",
        },
        ip_address=request.client.host if request.client else None,
    )
    
    return grn


@router.get("/api/v1/grn/{grn_id}")
async def get_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_read", "payments_read")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)
    items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id).all()

    grn_dict = {c.name: getattr(grn, c.name) for c in grn.__table__.columns}
    for k, v in grn_dict.items():
        if hasattr(v, 'hex'):
            grn_dict[k] = str(v)
        elif hasattr(v, 'isoformat'):
            grn_dict[k] = v.isoformat()

    is_partial_qty = str(grn.id) in _get_partial_qty_grn_ids(db, [grn.id])
    if grn.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == grn.purchase_order_id).first()
        if po:
            _enforce_owner(po, current_user)
        grn_dict["po_number"] = po.po_number if po else None
    else:
        grn_dict["po_number"] = None
    grn_dict["is_partial_qty"] = is_partial_qty
    grn_dict["status_display"] = _derive_grn_status_display(grn.status, is_partial_qty)

    # MCN-BUG-004: surface creator / reverser usernames (read-only) for the GRN view
    def _user_name(user_id) -> str | None:
        if not user_id:
            return None
        user = db.query(User).filter(User.id == user_id).first()
        return user.full_name if user else None

    grn_dict["created_by_name"] = _user_name(grn.created_by)
    grn_dict["reversed_by_name"] = _user_name(grn.reversed_by)

    return {"grn": grn_dict, "items": items}


@router.put("/api/v1/grn/{grn_id}")
async def update_grn(
    grn_id: UUID,
    payload: GRNCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft GRN can be edited")

    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")
    _enforce_owner(supplier, current_user)

    # Validate receipt date is not in the future
    from datetime import date
    if payload.receipt_date > date.today():
        raise HTTPException(status_code=400, detail="Receipt date cannot be a future date. Please select today or a past date.")

    # Recalculate payment due date: receipt_date + supplier payment_terms_days
    if payload.receipt_date and supplier.payment_terms_days:
        from datetime import timedelta
        grn.payment_due_date = payload.receipt_date + timedelta(days=supplier.payment_terms_days)

    po = None
    po_product_ids = set()
    po_items_by_id: dict[UUID, PurchaseOrderItem] = {}
    po_items_by_product: dict[UUID, list[PurchaseOrderItem]] = {}

    if payload.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.is_deleted == False).first()
        if not po:
            raise HTTPException(status_code=400, detail="Invalid purchase order")
        _enforce_owner(po, current_user)
        if po.status not in {"sent", "partial"}:
            raise HTTPException(status_code=400, detail="GRN can be created only from sent or partial purchase orders")
        if po.supplier_id != payload.supplier_id:
            raise HTTPException(status_code=400, detail="Supplier does not match selected purchase order")
        po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).all()
        po_product_ids = {item.product_id for item in po_items}
        po_items_by_id = {item.id: item for item in po_items}
        for po_item in po_items:
            po_items_by_product.setdefault(po_item.product_id, []).append(po_item)
        grn.under_delivery_tolerance = float(po.under_delivery_tolerance or 0)
        grn.over_delivery_tolerance = float(po.over_delivery_tolerance or 0)
    else:
        grn.under_delivery_tolerance = float(payload.under_delivery_tolerance or 0)
        grn.over_delivery_tolerance = float(payload.over_delivery_tolerance or 0)

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    grn.purchase_order_id = payload.purchase_order_id
    grn.supplier_id = payload.supplier_id
    grn.supplier_invoice_number = payload.supplier_invoice_number
    grn.supplier_invoice_date = payload.supplier_invoice_date
    grn.receipt_date = payload.receipt_date
    grn.notes = payload.notes

    db.query(GRNItem).filter(GRNItem.grn_id == grn_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for idx, item in enumerate(payload.items, start=1):
        resolved_po_item_id = item.purchase_order_item_id

        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)

        # GRN-007: MFG date must be a past date only
        from datetime import date
        if item.manufacture_date and item.manufacture_date >= date.today():
            raise HTTPException(
                status_code=400,
                detail="MFG Date must be a past date",
            )
        
        # GRN-008: Expiry date must be a future date only
        if item.expiry_date and item.expiry_date <= date.today():
            raise HTTPException(
                status_code=400,
                detail=f"Line item {idx}: expiry date must be a future date",
            )
        
        if item.manufacture_date and item.expiry_date and item.expiry_date < item.manufacture_date:
            raise HTTPException(
                status_code=400,
                detail=f"Line item {idx}: expiry date cannot be earlier than manufacture date",
            )

        if payload.purchase_order_id and po_product_ids and item.product_id not in po_product_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Product {product.name} is not part of the linked purchase order",
            )

        # PUR-006: Validate received quantity using tolerance in quantity units
        if payload.purchase_order_id:
            po_item = None
            if item.purchase_order_item_id:
                po_item = po_items_by_id.get(item.purchase_order_item_id)
            else:
                po_candidates = po_items_by_product.get(item.product_id, [])
                if len(po_candidates) == 1:
                    po_item = po_candidates[0]

            if not po_item:
                raise HTTPException(status_code=400, detail="Unable to map GRN line item to purchase order line item")

            resolved_po_item_id = po_item.id

            ordered_qty = float(po_item.quantity or 0)
            _validate_under_delivery_tolerance(float(grn.under_delivery_tolerance or 0), ordered_qty)
            previously_received_qty = float(po_item.received_quantity or 0)
            current_receipt_qty = float(item.quantity or 0)
            cumulative_received_qty = previously_received_qty + current_receipt_qty
            minimum_allowed = max(0.0, ordered_qty - float(grn.under_delivery_tolerance or 0))
            maximum_allowed = ordered_qty + float(grn.over_delivery_tolerance or 0)

            if cumulative_received_qty < minimum_allowed:
                raise HTTPException(status_code=400, detail="Under delivery exceeded allowed tolerance")
            if cumulative_received_qty > maximum_allowed:
                raise HTTPException(status_code=400, detail="Over delivery exceeded allowed tolerance")

        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(GRNItem(
            grn_id=grn.id,
            product_id=item.product_id,
            purchase_order_item_id=resolved_po_item_id,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    grn.subtotal = subtotal
    grn.total_discount = total_discount
    grn.total_taxable_amount = total_taxable
    grn.total_cgst = total_cgst
    grn.total_sgst = total_sgst
    grn.total_igst = total_igst
    grn.total_gst = total_cgst + total_sgst + total_igst
    grn.total_amount = total_taxable + grn.total_gst

    db.commit()
    db.refresh(grn)
    return grn


def _audit_value(value) -> str:
    """Render a GRN field value for the audit trail (old/new)."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@router.put("/api/v1/grn/{grn_id}/confirmed-details")
async def update_confirmed_grn(
    request: Request,
    grn_id: UUID,
    payload: GRNConfirmedEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    """MCN-BUG-004-ii: Edit detail fields of a CONFIRMED GRN.

    Unlocks Batch, Quantity, Rate, Expiry/MFG date and Remarks after confirmation for
    authorised users. Stock and purchase ledger postings are reconciled by reversing the
    GRN's original stock entries and re-posting the corrected values (the same mechanics as
    confirm/reverse), totals are recalculated (payables derive from GRN totals), and every
    field change is written to the audit trail. GRN number, supplier, created date/by are
    never modified here. Draft GRNs continue to use the standard edit form (PUT /api/v1/grn).
    """
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)
    if grn.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail="Only confirmed GRNs can be edited here. Draft GRNs use the standard edit form.",
        )

    if not payload.items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    # Financial-integrity guards (mirror reverse): editing quantity/rate would desync any
    # allocated payment or confirmed purchase return tied to this GRN.
    has_payment = (
        db.query(PaymentAllocation)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(
            PaymentAllocation.purchase_grn_id == grn_id,
            PaymentAllocation.is_deleted == False,
            Payment.is_deleted == False,
            Payment.status != "cancelled",
        )
        .first()
    )
    if has_payment:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit: a payment is allocated to this GRN. Cancel/bounce the payment first.",
        )

    has_return = (
        db.query(PurchaseReturn)
        .filter(
            PurchaseReturn.grn_id == grn_id,
            PurchaseReturn.is_deleted == False,
            PurchaseReturn.status == "confirmed",
        )
        .first()
    )
    if has_return:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit: a confirmed purchase return exists for this GRN.",
        )

    db_items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id, GRNItem.is_deleted == False).all()
    items_by_id = {str(i.id): i for i in db_items}

    tax_mode = determine_tax_mode(db, "supplier", grn.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    today = date.today()

    # Pass 1: validate every edit and compute net on-hand delta per product.
    net_delta_by_product: dict[UUID, float] = {}
    for edit in payload.items:
        item = items_by_id.get(str(edit.id))
        if not item:
            raise HTTPException(status_code=400, detail=f"GRN line item not found: {edit.id}")
        if edit.quantity is None or float(edit.quantity) <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        if float(edit.free_quantity or 0) < 0:
            raise HTTPException(status_code=400, detail="Free quantity cannot be negative")
        if edit.manufacture_date and edit.manufacture_date >= today:
            raise HTTPException(status_code=400, detail="MFG Date must be a past date")
        if edit.expiry_date and edit.expiry_date <= today:
            raise HTTPException(status_code=400, detail="Expiry date must be a future date")
        if edit.manufacture_date and edit.expiry_date and edit.expiry_date < edit.manufacture_date:
            raise HTTPException(status_code=400, detail="Expiry date cannot be earlier than manufacture date")
        old_total = float(item.quantity or 0) + float(item.free_quantity or 0)
        new_total = float(edit.quantity or 0) + float(edit.free_quantity or 0)
        net_delta_by_product[item.product_id] = net_delta_by_product.get(item.product_id, 0.0) + (new_total - old_total)

    # Guard: a reduction must not drive on-hand stock negative (already-issued goods).
    for product_id, delta in net_delta_by_product.items():
        if delta < -1e-9 and get_current_stock(db, product_id) + delta + 1e-6 < 0:
            product = db.query(Product).filter(Product.id == product_id).first()
            label = product.name if product else str(product_id)
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reduce received quantity for '{label}': the stock has already been issued.",
            )

    changes: list[dict] = []
    po_received_delta: dict[UUID, float] = {}

    for edit in payload.items:
        item = items_by_id[str(edit.id)]
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_label = product.name if product else str(item.product_id)
        old_qty = float(item.quantity or 0)
        old_free = float(item.free_quantity or 0)

        # Record field-level changes (BRD: field name, old value, new value).
        for field_name, old_value, new_value in (
            ("batch_no", item.batch_no, edit.batch_no),
            ("manufacture_date", item.manufacture_date, edit.manufacture_date),
            ("expiry_date", item.expiry_date, edit.expiry_date),
            ("quantity", item.quantity, edit.quantity),
            ("free_quantity", item.free_quantity, edit.free_quantity),
            ("unit_price", item.unit_price, edit.unit_price),
        ):
            if _audit_value(old_value) != _audit_value(new_value):
                changes.append({
                    "item_id": str(item.id),
                    "product": product_label,
                    "field": field_name,
                    "old_value": _audit_value(old_value),
                    "new_value": _audit_value(new_value),
                })

        # Reverse the original stock postings for this line (qty + free) at the old rate.
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="adjustment",
            reference_type="grn_edit_reversal",
            reference_id=grn.id,
            reference_number=f"{grn.grn_number}-EDIT-REV",
            quantity=-old_qty,
            rate=item.unit_price,
            transaction_date=today,
            created_by=current_user.id,
            notes="GRN post-confirmation edit: reverse original receipt",
        )
        if old_free > 0:
            add_stock_entry(
                db=db,
                product_id=item.product_id,
                transaction_type="adjustment",
                reference_type="grn_edit_reversal",
                reference_id=grn.id,
                reference_number=f"{grn.grn_number}-FREE-EDIT-REV",
                quantity=-old_free,
                rate=0,
                transaction_date=today,
                created_by=current_user.id,
                notes="GRN post-confirmation edit: reverse original free receipt",
            )

        # Recalculate line amounts (discount % and GST rate are unchanged by this edit).
        calc = calc_line_item(
            edit.quantity,
            edit.unit_price,
            float(item.discount_percent or 0),
            int(item.gst_rate or 0),
            is_igst,
            gst_applicable,
        )
        item.batch_no = edit.batch_no
        item.manufacture_date = edit.manufacture_date
        item.expiry_date = edit.expiry_date
        item.quantity = edit.quantity
        item.free_quantity = edit.free_quantity
        item.unit_price = edit.unit_price
        item.discount_amount = calc["discount"]
        item.taxable_amount = calc["taxable"]
        item.cgst_amount = calc["cgst"]
        item.sgst_amount = calc["sgst"]
        item.igst_amount = calc["igst"]
        item.total_amount = calc["total"]

        # Re-post the corrected receipt at the new quantity/rate.
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="purchase",
            reference_type="grn",
            reference_id=grn.id,
            reference_number=grn.grn_number,
            quantity=float(edit.quantity),
            rate=edit.unit_price,
            transaction_date=grn.receipt_date,
            created_by=current_user.id,
            notes="GRN post-confirmation edit: corrected receipt",
        )
        if float(edit.free_quantity or 0) > 0:
            add_stock_entry(
                db=db,
                product_id=item.product_id,
                transaction_type="purchase",
                reference_type="grn",
                reference_id=grn.id,
                reference_number=f"{grn.grn_number}-FREE",
                quantity=float(edit.free_quantity),
                rate=0,
                transaction_date=grn.receipt_date,
                created_by=current_user.id,
                notes="GRN post-confirmation edit: corrected free receipt",
            )

        if item.purchase_order_item_id:
            po_received_delta[item.purchase_order_item_id] = (
                po_received_delta.get(item.purchase_order_item_id, 0.0) + (float(edit.quantity) - old_qty)
            )

    # GRN-level remarks (notes).
    new_notes = payload.notes
    if _audit_value(grn.notes) != _audit_value(new_notes):
        changes.append({
            "item_id": None,
            "product": None,
            "field": "notes",
            "old_value": _audit_value(grn.notes),
            "new_value": _audit_value(new_notes),
        })
        grn.notes = new_notes

    if not changes:
        raise HTTPException(status_code=400, detail="No changes detected")

    # Adjust PO received quantities by the per-line delta and recompute PO status.
    for po_item_id, delta in po_received_delta.items():
        if abs(delta) < 1e-9:
            continue
        po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == po_item_id).first()
        if po_item:
            po_item.received_quantity = max(0.0, float(po_item.received_quantity or 0) + delta)

    db.flush()

    # Recompute GRN totals from the corrected line items.
    refreshed_items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id, GRNItem.is_deleted == False).all()
    grn.total_discount = sum(int(i.discount_amount or 0) for i in refreshed_items)
    grn.total_taxable_amount = sum(int(i.taxable_amount or 0) for i in refreshed_items)
    grn.total_cgst = sum(int(i.cgst_amount or 0) for i in refreshed_items)
    grn.total_sgst = sum(int(i.sgst_amount or 0) for i in refreshed_items)
    grn.total_igst = sum(int(i.igst_amount or 0) for i in refreshed_items)
    grn.subtotal = grn.total_taxable_amount + grn.total_discount
    grn.total_gst = grn.total_cgst + grn.total_sgst + grn.total_igst
    grn.total_amount = grn.total_taxable_amount + grn.total_gst

    if grn.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == grn.purchase_order_id).first()
        if po:
            _enforce_owner(po, current_user)
            if po.status not in {"cancelled"}:
                po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).all()
                if po_items:
                    has_any_receipt = any(float(i.received_quantity or 0) > 0 for i in po_items)
                    if not has_any_receipt:
                        po.status = "sent"
                    elif all(float(i.received_quantity or 0) >= float(i.quantity or 0) for i in po_items):
                        po.status = "received"
                    else:
                        po.status = "partial"

    refresh_materialized_view(db)
    db.commit()
    db.refresh(grn)

    log_audit_event(
        db,
        action=f"PUT:/api/v1/grn/{grn.id}/confirmed-details",
        resource_type="grn",
        status="success",
        user_id=current_user.id,
        resource_id=grn.id,
        details={
            "grn_number": grn.grn_number,
            "action": "edit_confirmed",
            "changes": changes,
            "edited_by": getattr(current_user, "email", None) or str(current_user.id),
            "edited_at": datetime.utcnow().isoformat(),
            "total_amount": grn.total_amount,
            "method": "PUT",
            "path": f"/api/v1/grn/{grn.id}/confirmed-details",
        },
        ip_address=request.client.host if request.client else None,
    )

    return grn


@router.post("/api/v1/grn/{grn_id}/confirm")
async def confirm_grn(
    request: Request,
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="GRN is not in draft status")

    # BUG-24: Guard against already completed POs
    if grn.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == grn.purchase_order_id).first()
        if po and po.status in {"received", "completed"}:
            raise HTTPException(status_code=400, detail="Purchase order is already fully received")

    grn.status = "confirmed"
    items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id).all()

    # BUG-01: Use stock service for entries + materialized view refresh
    for item in items:
        # Add received quantity to stock
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="purchase",
            reference_type="grn",
            reference_id=grn.id,
            reference_number=grn.grn_number,
            quantity=float(item.quantity),
            rate=item.unit_price,
            transaction_date=grn.receipt_date,
            created_by=current_user.id,
        )
        # Add free quantity to stock (at zero rate)
        if item.free_quantity and float(item.free_quantity) > 0:
            add_stock_entry(
                db=db,
                product_id=item.product_id,
                transaction_type="purchase",
                reference_type="grn",
                reference_id=grn.id,
                reference_number=f"{grn.grn_number}-FREE",
                quantity=float(item.free_quantity),
                rate=0,
                transaction_date=grn.receipt_date,
                created_by=current_user.id,
            )
        # Update PO item received_quantity
        if item.purchase_order_item_id:
            po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item.purchase_order_item_id).first()
            if po_item:
                po_item.received_quantity = float(po_item.received_quantity) + float(item.quantity)

    # Update PO status based on fulfillment
    if grn.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == grn.purchase_order_id).first()
        if po:
            _enforce_owner(po, current_user)
        if po and po.status not in {"received", "completed", "cancelled"}:
            po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).all()
            if po_items:
                has_any_receipt = any(float(i.received_quantity or 0) > 0 for i in po_items)
                if not has_any_receipt:
                    po.status = "sent"
                elif all(float(i.received_quantity or 0) >= float(i.quantity or 0) for i in po_items):
                    po.status = "received"
                else:
                    po.status = "partial"

    # BUG-01: Refresh materialized view after stock changes
    refresh_materialized_view(db)

    db.commit()
    db.refresh(grn)
    
    # Log audit event with GRN number
    log_audit_event(
        db,
        action=f"POST:/api/v1/grn/{grn.id}/confirm",
        resource_type="grn",
        status="success",
        user_id=current_user.id,
        resource_id=grn.id,
        details={
            "grn_number": grn.grn_number,
            "action": "confirm",
            "previous_status": "draft",
            "new_status": "confirmed",
            "supplier_id": str(grn.supplier_id),
            "total_amount": grn.total_amount,
            "purchase_order_id": str(grn.purchase_order_id) if grn.purchase_order_id else None,
            "method": "POST",
            "path": f"/api/v1/grn/{grn.id}/confirm",
        },
        ip_address=request.client.host if request.client else None,
    )
    
    return grn


@router.post("/api/v1/grn/{grn_id}/reverse")
async def reverse_grn(
    request: Request,
    grn_id: UUID,
    payload: GRNReverseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """MCN-BUG-004: Reverse a confirmed GRN — undo stock & ledger impact with reason + audit."""
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)
    if grn.status != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed GRNs can be reversed")

    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A reversal reason is required")

    items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id, GRNItem.is_deleted == False).all()

    # Guard 1: block reversal when payments are allocated against this GRN (financial integrity).
    has_payment = (
        db.query(PaymentAllocation)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(
            PaymentAllocation.purchase_grn_id == grn_id,
            PaymentAllocation.is_deleted == False,
            Payment.is_deleted == False,
            Payment.status != "cancelled",
        )
        .first()
    )
    if has_payment:
        raise HTTPException(
            status_code=400,
            detail="Cannot reverse: a payment is allocated to this GRN. Cancel/bounce the payment first.",
        )

    # Guard 2: block reversal when a confirmed purchase return exists against this GRN.
    has_return = (
        db.query(PurchaseReturn)
        .filter(
            PurchaseReturn.grn_id == grn_id,
            PurchaseReturn.is_deleted == False,
            PurchaseReturn.status == "confirmed",
        )
        .first()
    )
    if has_return:
        raise HTTPException(
            status_code=400,
            detail="Cannot reverse: a confirmed purchase return exists for this GRN.",
        )

    # Guard 3: block reversal when the received stock has already been consumed (would go negative).
    required_by_product: dict[UUID, float] = {}
    for item in items:
        qty = float(item.quantity or 0) + float(item.free_quantity or 0)
        required_by_product[item.product_id] = required_by_product.get(item.product_id, 0.0) + qty
    for product_id, qty_needed in required_by_product.items():
        if get_current_stock(db, product_id) + 1e-6 < qty_needed:
            product = db.query(Product).filter(Product.id == product_id).first()
            label = product.name if product else str(product_id)
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reverse: insufficient stock to undo receipt for '{label}' (already issued).",
            )

    # Reverse stock: negate the received and free quantities posted at confirm time.
    for item in items:
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="adjustment",
            reference_type="grn_reversal",
            reference_id=grn.id,
            reference_number=f"{grn.grn_number}-REV",
            quantity=-float(item.quantity),
            rate=item.unit_price,
            transaction_date=date.today(),
            created_by=current_user.id,
            notes=f"GRN reversal: {reason}",
        )
        if item.free_quantity and float(item.free_quantity) > 0:
            add_stock_entry(
                db=db,
                product_id=item.product_id,
                transaction_type="adjustment",
                reference_type="grn_reversal",
                reference_id=grn.id,
                reference_number=f"{grn.grn_number}-FREE-REV",
                quantity=-float(item.free_quantity),
                rate=0,
                transaction_date=date.today(),
                created_by=current_user.id,
                notes=f"GRN reversal (free qty): {reason}",
            )
        # Roll back PO item received_quantity.
        if item.purchase_order_item_id:
            po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item.purchase_order_item_id).first()
            if po_item:
                po_item.received_quantity = max(0.0, float(po_item.received_quantity or 0) - float(item.quantity))

    # Recompute PO status from remaining received quantities.
    if grn.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == grn.purchase_order_id).first()
        if po:
            _enforce_owner(po, current_user)
            if po.status not in {"cancelled"}:
                po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).all()
                if po_items:
                    has_any_receipt = any(float(i.received_quantity or 0) > 0 for i in po_items)
                    if not has_any_receipt:
                        po.status = "sent"
                    elif all(float(i.received_quantity or 0) >= float(i.quantity or 0) for i in po_items):
                        po.status = "received"
                    else:
                        po.status = "partial"

    grn.status = "reversed"
    grn.reversal_reason = reason
    grn.reversed_at = datetime.utcnow()
    grn.reversed_by = current_user.id

    refresh_materialized_view(db)
    db.commit()
    db.refresh(grn)

    log_audit_event(
        db,
        action=f"POST:/api/v1/grn/{grn.id}/reverse",
        resource_type="grn",
        status="success",
        user_id=current_user.id,
        resource_id=grn.id,
        details={
            "grn_number": grn.grn_number,
            "action": "reverse",
            "previous_status": "confirmed",
            "new_status": "reversed",
            "reason": reason,
            "supplier_id": str(grn.supplier_id),
            "total_amount": grn.total_amount,
            "purchase_order_id": str(grn.purchase_order_id) if grn.purchase_order_id else None,
            "method": "POST",
            "path": f"/api/v1/grn/{grn.id}/reverse",
        },
        ip_address=request.client.host if request.client else None,
    )

    return grn


@router.post("/api/v1/grn/{grn_id}/cancel")
async def cancel_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="Confirmed GRN cannot be cancelled")
    grn.status = "cancelled"
    db.commit()
    db.refresh(grn)
    return grn


@router.patch("/api/v1/grn/{grn_id}/archive")
async def archive_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    _enforce_owner(grn, current_user)

    grn.is_deleted = True
    grn.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(grn)
    return grn


@router.patch("/api/v1/grn/{grn_id}/restore")
async def restore_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == True).first()
    if not grn:
        raise HTTPException(status_code=404, detail="Archived GRN not found")
    _enforce_owner(grn, current_user)

    grn.is_deleted = False
    grn.deleted_at = None
    db.commit()
    db.refresh(grn)
    return grn


# ────────────────────────────── Purchase Returns ─────────────────────────────

@router.get("/api/v1/purchase-returns")
async def list_purchase_returns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_read")),
):
    query = db.query(PurchaseReturn).filter(PurchaseReturn.is_deleted == False)
    query = _scope_to_owner(query, PurchaseReturn, current_user)
    total = query.count()
    rows = query.order_by(PurchaseReturn.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/purchase-returns")
async def create_purchase_return(
    payload: PurchaseReturnCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == payload.grn_id, GoodsReceiptNote.status == "confirmed", GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=400, detail="Invalid confirmed GRN")
    _enforce_owner(grn, current_user)

    # BUG-02: Auto-detect GST mode based on supplier
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")
    _enforce_owner(supplier, current_user)
    _enforce_supplier_gstin_for_gst_purchase(supplier=supplier, gst_applicable=gst_applicable)

    # BUG-04: Safe return number generation
    return_number = generate_purchase_return_number(db)

    ret = PurchaseReturn(
        return_number=return_number,
        supplier_id=payload.supplier_id,
        grn_id=payload.grn_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status="draft",  # BUG-13: Always start as draft
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(ret)
    db.flush()

    subtotal = total_gst = 0
    for item in payload.items:
        grn_item = db.query(GRNItem).filter(GRNItem.id == item.grn_item_id).first() if item.grn_item_id else None
        if grn_item and float(item.quantity) > float(grn_item.quantity):
            raise HTTPException(status_code=400, detail="Return quantity exceeds received quantity")

        taxable = round(item.unit_price * item.quantity)
        # BUG-19: Use the correct IGST flag from the original transaction
        effective_gst_rate = item.gst_rate if gst_applicable else 0
        cgst, sgst, igst = split_tax(taxable, effective_gst_rate, is_igst, gst_applicable)
        total = taxable + cgst + sgst + igst
        db.add(PurchaseReturnItem(
            purchase_return_id=ret.id,
            product_id=item.product_id,
            grn_item_id=item.grn_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            taxable_amount=taxable,
            gst_rate=effective_gst_rate,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            total_amount=total,
        ))
        subtotal += taxable
        total_gst += cgst + sgst + igst

    ret.subtotal = subtotal
    ret.total_gst = total_gst
    ret.total_amount = subtotal + total_gst

    db.commit()
    db.refresh(ret)
    return ret


@router.get("/api/v1/purchase-returns/{return_id}")
async def get_purchase_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_read")),
):
    ret = db.query(PurchaseReturn).filter(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    _enforce_owner(ret, current_user)
    items = db.query(PurchaseReturnItem).filter(PurchaseReturnItem.purchase_return_id == return_id).all()
    return {"purchase_return": ret, "items": items}


@router.post("/api/v1/purchase-returns/{return_id}/confirm")
async def confirm_purchase_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_write")),
):
    ret = db.query(PurchaseReturn).filter(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    _enforce_owner(ret, current_user)
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase return can be confirmed")

    items = db.query(PurchaseReturnItem).filter(PurchaseReturnItem.purchase_return_id == return_id).all()
    
    # Pre-fetch batch snapshots and validate stock to prevent negative stock
    stock_cache = {}
    for item in items:
        grn_item = db.query(GRNItem).filter(GRNItem.id == item.grn_item_id).first() if item.grn_item_id else None
        batch_token = (grn_item.batch_no or "").strip() if grn_item else ""
        product_key = str(item.product_id)
        cache_key = f"{product_key}_{batch_token}"

        if cache_key not in stock_cache:
            if batch_token:
                batch_snapshots = get_product_batch_snapshot(db, item.product_id)
                stock_cache[cache_key] = float(batch_snapshots.get(batch_token, {}).get("available_qty", 0.0))
            else:
                stock_cache[cache_key] = get_current_stock(db, item.product_id)

        qty = float(item.quantity)
        if stock_cache[cache_key] < qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock to return product {item.product_id}")
            
        stock_cache[cache_key] -= qty

    for item in items:
        # BUG-01: Use stock service with reference_id
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="purchase_return",
            reference_type="purchase_return",
            reference_id=ret.id,
            reference_number=ret.return_number,
            quantity=-float(item.quantity),
            rate=item.unit_price,
            transaction_date=ret.return_date,
            created_by=current_user.id,
        )

    # BUG-01: Refresh materialized view
    refresh_materialized_view(db)

    ret.status = "confirmed"
    db.commit()
    db.refresh(ret)
    return ret


# BUG-16: Cancel no longer requires a body payload
@router.post("/api/v1/purchase-returns/{return_id}/cancel")
async def cancel_purchase_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_write")),
):
    ret = db.query(PurchaseReturn).filter(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    _enforce_owner(ret, current_user)
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase return can be cancelled")
    ret.status = "cancelled"
    db.commit()
    db.refresh(ret)
    return ret


# ────────────────────────────── PO PDF Download ──────────────────────────────

@router.get("/api/v1/purchase-orders/{po_id}/pdf")
async def download_po_pdf(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_read", "payments_read")),
):
    """Download Purchase Order as a professional PDF."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_po_pdf

    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    _enforce_owner(po, current_user)

    pdf_bytes = generate_po_pdf(db, po_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={po.po_number}.pdf"},
    )


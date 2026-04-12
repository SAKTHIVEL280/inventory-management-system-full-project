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
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
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
from app.schemas.purchase import (
    PurchaseOrderCreateRequest,
    PurchaseOrderStatusRequest,
    GRNCreateRequest,
    PurchaseReturnCreateRequest,
)
from app.services.order_number_service import (
    generate_po_number,
    generate_grn_number,
    generate_purchase_return_number,
)
from app.services.gst_service import determine_tax_mode, calc_line_item, split_tax
from app.services.stock_service import add_stock_entry, refresh_materialized_view

router = APIRouter(tags=["purchase"])


def _derive_grn_status_display(raw_status: str | None, is_partial_qty: bool) -> str:
    status = (raw_status or "").strip().lower()
    if status == "draft":
        return "Partial Receipt (Draft)" if is_partial_qty else "Draft"
    if status == "confirmed":
        return "Partial Receipt (Confirmed)" if is_partial_qty else "Confirmed"
    if status == "cancelled":
        return "Cancelled"
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
    current_user: User = Depends(require_permissions("purchase_orders_read")),
):
    query = db.query(PurchaseOrder)
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
    payload: PurchaseOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    # BUG-02: Auto-detect GST mode based on supplier country/state
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

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
        created_by=current_user.id,
    )
    db.add(po)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
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
    return po


@router.get("/api/v1/purchase-orders/{po_id}")
async def get_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_read")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
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
    if po.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase orders can be edited")

    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

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
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

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
    current_user: User = Depends(require_permissions("grn_read")),
):
    query = db.query(GoodsReceiptNote)
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
    return grn


@router.get("/api/v1/grn/{grn_id}")
async def get_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_read")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
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
        grn_dict["po_number"] = po.po_number if po else None
    else:
        grn_dict["po_number"] = None
    grn_dict["is_partial_qty"] = is_partial_qty
    grn_dict["status_display"] = _derive_grn_status_display(grn.status, is_partial_qty)

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
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft GRN can be edited")

    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

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


@router.post("/api/v1/grn/{grn_id}/confirm")
async def confirm_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
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

    # BUG-02: Auto-detect GST mode based on supplier
    tax_mode = determine_tax_mode(db, "supplier", payload.supplier_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    # BUG-04: Safe return number generation
    return_number = generate_purchase_return_number(db)

    ret = PurchaseReturn(
        return_number=return_number,
        supplier_id=payload.supplier_id,
        grn_id=payload.grn_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status="draft",  # BUG-13: Always start as draft
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
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase return can be confirmed")

    items = db.query(PurchaseReturnItem).filter(PurchaseReturnItem.purchase_return_id == return_id).all()
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
    current_user: User = Depends(require_permissions("purchase_orders_read")),
):
    """Download Purchase Order as a professional PDF."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_po_pdf

    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    pdf_bytes = generate_po_pdf(db, po_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={po.po_number}.pdf"},
    )


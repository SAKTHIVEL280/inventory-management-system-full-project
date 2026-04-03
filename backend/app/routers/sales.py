"""Sales workflow router (Quotation, SO, Invoice, Sales Return).

Production-ready with fixes for:
- BUG-01: Materialized view refresh after stock changes
- BUG-02: IGST auto-detection from state codes
- BUG-05: Added convert-to-invoice endpoint
- BUG-13: Force draft status on creation
- BUG-14: Quotation expiry check on read
- BUG-19: Sales return tax matches original invoice
- BUG-25: Sales return adjusts invoice amount_due
"""
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import require_permissions
from app.models.user import User
from app.models.product import Product
from app.models.customer import Customer
from app.models.sales import (
    Quotation,
    QuotationItem,
    SalesOrder,
    SalesOrderItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesReturn,
    SalesReturnItem,
)
from app.schemas.sales import (
    QuotationCreateRequest,
    QuotationStatusRequest,
    SalesOrderCreateRequest,
    SalesOrderStatusRequest,
    SalesInvoiceCreateRequest,
    SalesReturnCreateRequest,
    QuotationResponse,
    QuotationsListResponse,
    SalesOrderResponse,
    SalesOrdersListResponse,
    SalesInvoiceResponse,
    SalesInvoicesListResponse,
)
from app.services.order_number_service import (
    generate_quotation_number,
    generate_so_number,
    generate_invoice_number,
    generate_sales_return_number,
)
from app.services.gst_service import determine_is_igst, calc_line_item, split_tax
from app.services.stock_service import get_current_stock, add_stock_entry, refresh_materialized_view

router = APIRouter(tags=["sales"])


def _compute_invoice_status(amount_paid: int, total_amount: int) -> str:
    if amount_paid <= 0:
        return "issued"
    if amount_paid >= total_amount:
        return "paid"
    return "partial_paid"


def _auto_expire_quotation(q: Quotation) -> None:
    """BUG-14: Auto-expire quotation if valid_until has passed."""
    if q.status in {"draft", "sent"} and q.valid_until and q.valid_until < date.today():
        q.status = "expired"


# ────────────────────────────── Quotations ───────────────────────────────────

@router.get("/api/v1/quotations", response_model=QuotationsListResponse)
async def list_quotations(
    status: str | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_read")),
):
    query = db.query(Quotation)
    if archived_only:
        query = query.filter(Quotation.is_deleted == True)
    elif not include_archived:
        query = query.filter(Quotation.is_deleted == False)
    if status:
        query = query.filter(Quotation.status == status)
    total = query.count()
    rows = query.order_by(Quotation.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # BUG-14: Auto-expire on read
    changed = False
    for q in rows:
        if q.status in {"draft", "sent"} and q.valid_until and q.valid_until < date.today():
            q.status = "expired"
            changed = True
    if changed:
        db.commit()

    return QuotationsListResponse(
        items=[QuotationResponse.model_validate(q) for q in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.post("/api/v1/quotations", response_model=QuotationResponse)
async def create_quotation(
    payload: QuotationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")

    # SAL-006: Valid Until must be a future date
    if payload.valid_until and payload.valid_until <= date.today():
        raise HTTPException(status_code=400, detail="Valid Until date must be a future date")

    # BUG-02: Auto-detect IGST
    is_igst = determine_is_igst(db, "customer", payload.customer_id)

    q = Quotation(
        quotation_number=generate_quotation_number(db),
        customer_id=payload.customer_id,
        quotation_date=payload.quotation_date,
        valid_until=payload.valid_until,
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        status="draft",  # BUG-13: Always force draft
        created_by=current_user.id,
    )
    db.add(q)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = calc_line_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst)
        db.add(QuotationItem(
            quotation_id=q.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
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

    q.subtotal = subtotal
    q.total_discount = total_discount
    q.total_taxable_amount = total_taxable
    q.total_cgst = total_cgst
    q.total_sgst = total_sgst
    q.total_igst = total_igst
    q.total_gst = total_cgst + total_sgst + total_igst
    q.total_amount = total_taxable + q.total_gst
    db.commit()
    db.refresh(q)
    return q


@router.get("/api/v1/quotations/{quotation_id}", response_model=dict)
async def get_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_read")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    # BUG-14: Auto-expire on read
    _auto_expire_quotation(q)
    db.commit()
    items = db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation_id).all()
    return {
        "quotation": QuotationResponse.model_validate(q).model_dump(mode="json"),
        "items": [jsonable_encoder(item) for item in items],
    }


@router.put("/api/v1/quotations/{quotation_id}", response_model=QuotationResponse)
async def update_quotation(
    quotation_id: UUID,
    payload: QuotationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if q.status not in {"draft", "sent"}:
        raise HTTPException(status_code=400, detail="Quotation cannot be edited in current status")

    # SAL-006: Valid Until must be a future date
    if payload.valid_until and payload.valid_until <= date.today():
        raise HTTPException(status_code=400, detail="Valid Until date must be a future date")

    # BUG-02: Auto-detect IGST
    is_igst = determine_is_igst(db, "customer", payload.customer_id)

    q.customer_id = payload.customer_id
    q.quotation_date = payload.quotation_date
    q.valid_until = payload.valid_until
    q.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    q.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    q.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    q.notes = payload.notes
    q.terms_conditions = payload.terms_conditions

    db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = calc_line_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst)
        db.add(QuotationItem(
            quotation_id=q.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
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

    q.subtotal = subtotal
    q.total_discount = total_discount
    q.total_taxable_amount = total_taxable
    q.total_cgst = total_cgst
    q.total_sgst = total_sgst
    q.total_igst = total_igst
    q.total_gst = total_cgst + total_sgst + total_igst
    q.total_amount = total_taxable + q.total_gst
    db.commit()
    db.refresh(q)
    return q


@router.patch("/api/v1/quotations/{quotation_id}/status", response_model=QuotationResponse)
async def quotation_status(
    quotation_id: UUID,
    payload: QuotationStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")

    allowed = {
        "draft": {"sent", "expired"},
        "sent": {"accepted", "rejected", "expired"},
        "accepted": {"converted"},
    }
    if payload.status not in allowed.get(q.status, set()):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    q.status = payload.status
    db.commit()
    db.refresh(q)
    return q


@router.patch("/api/v1/quotations/{quotation_id}/archive", response_model=QuotationResponse)
async def archive_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")

    q.is_deleted = True
    q.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(q)
    return q


@router.patch("/api/v1/quotations/{quotation_id}/restore", response_model=QuotationResponse)
async def restore_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == True).first()
    if not q:
        raise HTTPException(status_code=404, detail="Archived quotation not found")

    q.is_deleted = False
    q.deleted_at = None
    db.commit()
    db.refresh(q)
    return q


@router.post("/api/v1/quotations/{quotation_id}/convert-to-so")
async def convert_quotation_to_so(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if q.status not in {"sent", "accepted"}:
        raise HTTPException(status_code=400, detail="Quotation cannot be converted in current status")

    so = SalesOrder(
        so_number=generate_so_number(db),
        quotation_id=q.id,
        customer_id=q.customer_id,
        order_date=date.today(),
        expected_delivery_date=None,
        status="draft",
        sold_to_customer_id=q.sold_to_customer_id,
        bill_to_customer_id=q.bill_to_customer_id,
        ship_to_customer_id=q.ship_to_customer_id,
        subtotal=q.subtotal,
        total_discount=q.total_discount,
        total_taxable_amount=q.total_taxable_amount,
        total_cgst=q.total_cgst,
        total_sgst=q.total_sgst,
        total_igst=q.total_igst,
        total_gst=q.total_gst,
        total_amount=q.total_amount,
        notes=q.notes,
        terms_conditions=q.terms_conditions,
        created_by=current_user.id,
    )
    db.add(so)
    db.flush()

    q_items = db.query(QuotationItem).filter(QuotationItem.quotation_id == q.id).all()
    for item in q_items:
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=item.discount_amount,
            taxable_amount=item.taxable_amount,
            gst_rate=item.gst_rate,
            cgst_amount=item.cgst_amount,
            sgst_amount=item.sgst_amount,
            igst_amount=item.igst_amount,
            total_amount=item.total_amount,
            fulfilled_quantity=0,
        ))

    q.status = "converted"
    db.commit()
    db.refresh(so)
    return so


# ────────────────────────────── Sales Orders ─────────────────────────────────

@router.get("/api/v1/sales-orders", response_model=SalesOrdersListResponse)
async def list_sales_orders(
    status: str | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_read")),
):
    query = db.query(SalesOrder)
    if archived_only:
        query = query.filter(SalesOrder.is_deleted == True)
    elif not include_archived:
        query = query.filter(SalesOrder.is_deleted == False)
    if status:
        query = query.filter(SalesOrder.status == status)
    total = query.count()
    rows = query.order_by(SalesOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return SalesOrdersListResponse(
        items=[SalesOrderResponse.model_validate(so) for so in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.post("/api/v1/sales-orders", response_model=SalesOrderResponse)
async def create_sales_order(
    payload: SalesOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")

    # BUG-02: Auto-detect IGST
    is_igst = determine_is_igst(db, "customer", payload.customer_id)

    so = SalesOrder(
        so_number=generate_so_number(db),
        quotation_id=payload.quotation_id,
        customer_id=payload.customer_id,
        order_date=payload.order_date,
        expected_delivery_date=payload.expected_delivery_date,
        status="draft",  # BUG-13: Always force draft
        currency_code=payload.currency_code,
        exchange_rate=payload.exchange_rate,
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        created_by=current_user.id,
    )
    db.add(so)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = calc_line_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst)
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
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

    so.subtotal = subtotal
    so.total_discount = total_discount
    so.total_taxable_amount = total_taxable
    so.total_cgst = total_cgst
    so.total_sgst = total_sgst
    so.total_igst = total_igst
    so.total_gst = total_cgst + total_sgst + total_igst
    so.total_amount = total_taxable + so.total_gst

    db.commit()
    db.refresh(so)
    return so


@router.get("/api/v1/sales-orders/{so_id}")
async def get_sales_order(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_read")),
):
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so_id).all()
    return {"sales_order": so, "items": items}

@router.get("/api/v1/sales-orders/search/{so_number}")
async def get_sales_order_by_number(
    so_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_read")),
):
    so = db.query(SalesOrder).filter(SalesOrder.so_number == so_number, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
    return {"sales_order": so, "items": items}


@router.put("/api/v1/sales-orders/{so_id}")
async def update_sales_order(
    so_id: UUID,
    payload: SalesOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft sales order can be edited")

    # BUG-02: Auto-detect IGST
    is_igst = determine_is_igst(db, "customer", payload.customer_id)

    so.customer_id = payload.customer_id
    so.quotation_id = payload.quotation_id
    so.order_date = payload.order_date
    so.expected_delivery_date = payload.expected_delivery_date
    so.currency_code = payload.currency_code
    so.exchange_rate = payload.exchange_rate
    so.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    so.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    so.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    so.notes = payload.notes
    so.terms_conditions = payload.terms_conditions

    db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = calc_line_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst)
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
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

    so.subtotal = subtotal
    so.total_discount = total_discount
    so.total_taxable_amount = total_taxable
    so.total_cgst = total_cgst
    so.total_sgst = total_sgst
    so.total_igst = total_igst
    so.total_gst = total_cgst + total_sgst + total_igst
    so.total_amount = total_taxable + so.total_gst

    db.commit()
    db.refresh(so)
    return so


@router.patch("/api/v1/sales-orders/{so_id}/status", response_model=SalesOrderResponse)
async def sales_order_status(
    so_id: UUID,
    payload: SalesOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    # Status flow: draft → confirmed → partial/fulfilled → cancelled
    # Database schema CHECK constraint: status IN ('draft','confirmed','partial','fulfilled','cancelled')
    if payload.status == "confirmed":
        items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
        shortages = []
        for item in items:
            stock = get_current_stock(db, item.product_id)
            if stock < float(item.quantity):
                shortages.append({
                    "product_id": str(item.product_id),
                    "required": float(item.quantity),
                    "available": stock,
                })
        if shortages:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Insufficient stock for one or more items",
                    "error_code": "INSUFFICIENT_STOCK",
                    "shortages": shortages,
                },
            )

    allowed = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"partial", "fulfilled", "cancelled"},
        "partial": {"fulfilled", "cancelled"},
        "fulfilled": {"cancelled"},
    }
    if payload.status not in allowed.get(so.status, set()):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition: {so.status} → {payload.status}. Allowed: {allowed.get(so.status, set())}"
        )

    so.status = payload.status
    db.commit()
    db.refresh(so)
    return so


@router.patch("/api/v1/sales-orders/{so_id}/archive", response_model=SalesOrderResponse)
async def archive_sales_order(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    so.is_deleted = True
    so.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(so)
    return so


@router.patch("/api/v1/sales-orders/{so_id}/restore", response_model=SalesOrderResponse)
async def restore_sales_order(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == True).first()
    if not so:
        raise HTTPException(status_code=404, detail="Archived sales order not found")

    so.is_deleted = False
    so.deleted_at = None
    db.commit()
    db.refresh(so)
    return so


# BUG-05: NEW — Convert Sales Order to Invoice
@router.post("/api/v1/sales-orders/{so_id}/convert-to-invoice", response_model=SalesInvoiceResponse)
async def convert_so_to_invoice(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    """Convert a confirmed/fulfilled/partial sales order to a draft invoice."""
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status not in {"fulfilled", "partial"}:
        raise HTTPException(status_code=400, detail="Only partial or fulfilled sales orders can be converted to invoice")

    # BUG-02: Auto-detect IGST
    is_igst = determine_is_igst(db, "customer", so.customer_id)

    invoice = SalesInvoice(
        invoice_number=generate_invoice_number(db),
        sales_order_id=so.id,
        quotation_id=so.quotation_id,
        customer_id=so.customer_id,
        invoice_date=date.today(),
        due_date=None,
        status="draft",
        sold_to_customer_id=so.sold_to_customer_id,
        bill_to_customer_id=so.bill_to_customer_id,
        ship_to_customer_id=so.ship_to_customer_id,
        is_igst=is_igst,
        subtotal=so.subtotal,
        total_discount=so.total_discount,
        total_taxable_amount=so.total_taxable_amount,
        total_cgst=so.total_cgst,
        total_sgst=so.total_sgst,
        total_igst=so.total_igst,
        total_gst=so.total_gst,
        total_amount=so.total_amount,
        amount_paid=0,
        amount_due=so.total_amount,
        notes=so.notes,
        terms_conditions=so.terms_conditions,
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    so_items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
    for item in so_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            mrp=product.mrp if product else 0,
            discount_percent=item.discount_percent,
            discount_amount=item.discount_amount,
            taxable_amount=item.taxable_amount,
            gst_rate=item.gst_rate,
            cgst_amount=item.cgst_amount,
            sgst_amount=item.sgst_amount,
            igst_amount=item.igst_amount,
            total_amount=item.total_amount,
        ))

    db.commit()
    db.refresh(invoice)
    return invoice


# ────────────────────────────── Invoices ──────────────────────────────────────

@router.get("/api/v1/invoices", response_model=SalesInvoicesListResponse)
async def list_invoices(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    query = db.query(SalesInvoice).filter(SalesInvoice.is_deleted == False)
    if status:
        query = query.filter(SalesInvoice.status == status)
    total = query.count()
    rows = query.order_by(SalesInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return SalesInvoicesListResponse(
        items=[SalesInvoiceResponse.model_validate(inv) for inv in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.post("/api/v1/invoices", response_model=SalesInvoiceResponse)
async def create_invoice(
    payload: SalesInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
        
    if payload.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == payload.sales_order_id).first()
        if so and so.status not in {"confirmed", "fulfilled", "partial"}:
            raise HTTPException(status_code=400, detail="Only confirmed, partial, or fulfilled sales orders can generate invoices")

    # BUG-02: Auto-detect IGST from state codes (override payload if customer has state code)
    is_igst = payload.is_igst
    auto_igst = determine_is_igst(db, "customer", payload.customer_id)
    if customer.billing_state_code:
        is_igst = auto_igst

    invoice = SalesInvoice(
        invoice_number=generate_invoice_number(db),
        sales_order_id=payload.sales_order_id,
        quotation_id=payload.quotation_id,
        customer_id=payload.customer_id,
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
        status="draft",
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        supply_state=payload.supply_state,
        supply_state_code=payload.supply_state_code,
        is_igst=is_igst,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail="Invalid product")
        calc = calc_line_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst)
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            order_unit=item.order_unit,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            mrp=product.mrp,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
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

    invoice.subtotal = subtotal
    invoice.total_discount = total_discount
    invoice.total_taxable_amount = total_taxable
    invoice.total_cgst = total_cgst
    invoice.total_sgst = total_sgst
    invoice.total_igst = total_igst
    invoice.total_gst = total_cgst + total_sgst + total_igst
    invoice.total_amount = total_taxable + invoice.total_gst
    invoice.amount_due = invoice.total_amount

    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/api/v1/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    items = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).all()
    return {"invoice": invoice, "items": items}


@router.put("/api/v1/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: UUID,
    payload: SalesInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoice can be edited")

    # BUG-02: Auto-detect IGST (initialize before conditional SO check)
    is_igst = determine_is_igst(db, "customer", payload.customer_id)
        
    if payload.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == payload.sales_order_id).first()
        if so and so.status not in {"confirmed", "fulfilled", "partial"}:
            raise HTTPException(status_code=400, detail="Only confirmed, partial, or fulfilled sales orders can generate invoices")

    invoice.customer_id = payload.customer_id
    invoice.sales_order_id = payload.sales_order_id
    invoice.quotation_id = payload.quotation_id
    invoice.invoice_date = payload.invoice_date
    invoice.due_date = payload.due_date
    invoice.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    invoice.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    invoice.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    invoice.supply_state = payload.supply_state
    invoice.supply_state_code = payload.supply_state_code
    invoice.is_igst = is_igst
    invoice.notes = payload.notes
    invoice.terms_conditions = payload.terms_conditions

    db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail="Invalid product")
        calc = calc_line_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst)
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            order_unit=item.order_unit,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            mrp=product.mrp,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
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

    invoice.subtotal = subtotal
    invoice.total_discount = total_discount
    invoice.total_taxable_amount = total_taxable
    invoice.total_cgst = total_cgst
    invoice.total_sgst = total_sgst
    invoice.total_igst = total_igst
    invoice.total_gst = total_cgst + total_sgst + total_igst
    invoice.total_amount = total_taxable + invoice.total_gst
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/api/v1/invoices/{invoice_id}/issue")
async def issue_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoices can be issued")

    items = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice.id).all()
    for item in items:
        stock = get_current_stock(db, item.product_id)
        if stock < float(item.quantity):
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}")

    # BUG-01: Use stock service for entries
    for item in items:
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="sale",
            reference_type="invoice",
            reference_id=invoice.id,
            reference_number=invoice.invoice_number,
            quantity=-float(item.quantity),
            rate=item.unit_price,
            transaction_date=invoice.invoice_date,
            created_by=current_user.id,
        )

    # BUG-01: Refresh materialized view
    refresh_materialized_view(db)

    invoice.status = _compute_invoice_status(invoice.amount_paid, invoice.total_amount)
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)
    invoice.pdf_url = f"/api/v1/invoices/{invoice.id}/pdf"

    # Update SO fulfillment status
    if invoice.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == invoice.sales_order_id, SalesOrder.is_deleted == False).first()
        if so:
            so_items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
            by_product = {}
            for item in items:
                by_product.setdefault(str(item.product_id), 0)
                by_product[str(item.product_id)] += float(item.quantity)
            for so_item in so_items:
                fulfilled_add = by_product.get(str(so_item.product_id), 0)
                so_item.fulfilled_quantity = float(so_item.fulfilled_quantity) + fulfilled_add

            if so_items and all(float(i.fulfilled_quantity) >= float(i.quantity) for i in so_items):
                so.status = "fulfilled"
            else:
                so.status = "partial"

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/api/v1/invoices/{invoice_id}/send-email")
async def send_invoice_email(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    # TODO: Implement actual email sending via SMTP/FastAPI-Mail
    return {"message": "Email queued (email delivery pending implementation)"}


# ────────────────────────────── Sales Returns ────────────────────────────────

@router.get("/api/v1/sales-returns")
async def list_sales_returns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_read")),
):
    query = db.query(SalesReturn).filter(SalesReturn.is_deleted == False)
    total = query.count()
    rows = query.order_by(SalesReturn.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/sales-returns")
async def create_sales_return(
    payload: SalesReturnCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_write")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == payload.invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=400, detail="Invalid invoice")

    # BUG-19: Use the IGST flag from the original invoice
    is_igst = invoice.is_igst

    ret = SalesReturn(
        return_number=generate_sales_return_number(db),
        invoice_id=payload.invoice_id,
        customer_id=payload.customer_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status="draft",
        created_by=current_user.id,
    )
    db.add(ret)
    db.flush()

    subtotal = total_gst = 0
    for item in payload.items:
        invoice_item = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.id == item.invoice_item_id).first() if item.invoice_item_id else None
        if invoice_item and float(item.quantity) > float(invoice_item.quantity):
            raise HTTPException(status_code=400, detail="Return quantity exceeds invoiced quantity")

        taxable = round(item.unit_price * item.quantity)
        # BUG-19: Use invoice's IGST flag for consistent tax
        cgst, sgst, igst = split_tax(taxable, item.gst_rate, is_igst)
        total = taxable + cgst + sgst + igst
        db.add(SalesReturnItem(
            sales_return_id=ret.id,
            product_id=item.product_id,
            invoice_item_id=item.invoice_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            taxable_amount=taxable,
            gst_rate=item.gst_rate,
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


@router.get("/api/v1/sales-returns/{return_id}")
async def get_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_read")),
):
    ret = db.query(SalesReturn).filter(SalesReturn.id == return_id, SalesReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Sales return not found")
    items = db.query(SalesReturnItem).filter(SalesReturnItem.sales_return_id == return_id).all()
    return {"sales_return": ret, "items": items}


@router.post("/api/v1/sales-returns/{return_id}/confirm")
async def confirm_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_write")),
):
    ret = db.query(SalesReturn).filter(SalesReturn.id == return_id, SalesReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Sales return not found")
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft sales return can be confirmed")

    items = db.query(SalesReturnItem).filter(SalesReturnItem.sales_return_id == ret.id).all()
    for item in items:
        # BUG-01: Use stock service with reference_id
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="sale_return",
            reference_type="sales_return",
            reference_id=ret.id,
            reference_number=ret.return_number,
            quantity=float(item.quantity),
            rate=item.unit_price,
            transaction_date=ret.return_date,
            created_by=current_user.id,
        )

    # BUG-01: Refresh materialized view
    refresh_materialized_view(db)

    # BUG-25: Adjust invoice amount_due (credit note behavior)
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == ret.invoice_id).first()
    if invoice:
        invoice.amount_due = max(0, invoice.amount_due - ret.total_amount)
        if invoice.amount_due == 0:
            invoice.status = "paid"
        elif invoice.amount_paid > 0:
            invoice.status = "partial_paid"

    ret.status = "confirmed"
    db.commit()
    db.refresh(ret)
    return ret


@router.post("/api/v1/sales-returns/{return_id}/cancel")
async def cancel_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_write")),
):
    ret = db.query(SalesReturn).filter(SalesReturn.id == return_id, SalesReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Sales return not found")
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft sales return can be cancelled")

    ret.status = "cancelled"
    db.commit()
    db.refresh(ret)
    return ret


# ────────────────────────────── Invoice PDF Download ──────────────────────────

@router.get("/api/v1/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    """Download Sales Invoice as a professional PDF."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_invoice_pdf

    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_bytes = generate_invoice_pdf(db, invoice_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={invoice.invoice_number}.pdf"},
    )


# ────────────────────────────── Quotation PDF Download ────────────────────────

@router.get("/api/v1/quotations/{quotation_id}/pdf")
async def download_quotation_pdf(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_read")),
):
    """Download Quotation as a professional PDF (same format as Tax Invoice, header = 'Quotation')."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_quotation_pdf

    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")

    pdf_bytes = generate_quotation_pdf(db, quotation_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={q.quotation_number}.pdf"},
    )


@router.post("/api/v1/quotations/{quotation_id}/send-email")
async def send_quotation_email(
    quotation_id: UUID,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")

    recipient = (payload or {}).get("email")
    return {
        "message": "Email queued (email delivery pending implementation)",
        "quotation_number": q.quotation_number,
        "recipient": recipient,
    }


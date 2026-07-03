"""Return Delivery Note (RDN) endpoints."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.database import get_db
from app.dependencies import require_permissions, require_role, scope_query_to_company
from app.models.customization_option import CustomizationOption
from app.models.customer import Customer
from app.models.product import Product
from app.models.rdn import ReturnDeliveryNote, ReturnDeliveryNoteItem, RdnCreditNote, RdnCreditNoteItem
from app.models.product import StockLedger
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.models.user import User
from app.schemas.rdn import (
    RDNCreateRequest,
    RDNOverviewResponse,
    RDNResponse,
    RDNUpdateRequest,
    RDNCreditNoteDetailResponse,
    RDNCreditNoteOverviewResponse,
    RDNCreditNoteResponse,
)
from app.services.audit_service import log_audit_event
from app.services.auth_service import normalize_role, PRIVILEGED_ROLES
from app.services.gst_service import calc_line_item, invoice_type_tax_mode
from app.services.order_number_service import generate_rdn_number
from app.services.stock_service import add_stock_entry, refresh_materialized_view
from app.utils.input_validation import normalize_search_query
from app.utils.rounding import round_paise_to_nearest_5

router = APIRouter(tags=["rdn"])


def _scope_to_owner(query, model_cls, current_user: User):
    if current_user.company_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a company")
    query = scope_query_to_company(query, model_cls, current_user.company_id)
    if normalize_role(current_user.role) in PRIVILEGED_ROLES:
        return query
    owner_col = getattr(model_cls, "created_by", None)
    if owner_col is None:
        return query
    return query.filter(owner_col == current_user.id)


def _enforce_owner(row, current_user: User) -> None:
    if getattr(row, "company_id", None) is None:
        return
    if row.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Forbidden")


def _load_return_reason_map(db: Session, company_id) -> dict[str, str]:
    rows = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.company_id == company_id,
            CustomizationOption.module == "rdn",
            CustomizationOption.field_name == "return_reason",
            CustomizationOption.is_active == True,
            CustomizationOption.is_deleted == False,
        )
        .order_by(CustomizationOption.sort_order.asc(), CustomizationOption.option_value.asc())
        .all()
    )
    return {row.option_value: (row.display_label or row.option_value) for row in rows}


def _make_batch_key(product_id: UUID, batch_no: str | None) -> str:
    return f"{product_id}::{(batch_no or '').strip()}"


def _invoice_batch_quantities(
    db: Session,
    invoice_id: UUID,
) -> dict[str, float]:
    rows = (
        db.query(
            SalesInvoiceItem.product_id,
            SalesInvoiceItem.batch_no,
            func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("qty"),
        )
        .filter(
            SalesInvoiceItem.invoice_id == invoice_id,
            SalesInvoiceItem.is_deleted == False,
        )
        .group_by(SalesInvoiceItem.product_id, SalesInvoiceItem.batch_no)
        .all()
    )
    return {
        _make_batch_key(row.product_id, row.batch_no): float(row.qty or 0)
        for row in rows
    }


def _pending_invoice_batch_quantities(
    db: Session,
    invoice_id: UUID,
    *,
    exclude_rdn_id: UUID | None = None,
) -> dict[str, float]:
    rows = (
        db.query(
            ReturnDeliveryNoteItem.product_id,
            ReturnDeliveryNoteItem.batch_no,
            func.coalesce(func.sum(ReturnDeliveryNoteItem.return_quantity), 0).label("qty"),
        )
        .join(ReturnDeliveryNote, ReturnDeliveryNoteItem.rdn_id == ReturnDeliveryNote.id)
        .filter(
            ReturnDeliveryNote.sales_invoice_id == invoice_id,
            ReturnDeliveryNote.status.in_(["draft", "confirmed"]),
            ReturnDeliveryNote.is_deleted == False,
            ReturnDeliveryNoteItem.is_deleted == False,
        )
        .group_by(ReturnDeliveryNoteItem.product_id, ReturnDeliveryNoteItem.batch_no)
    )
    if exclude_rdn_id is not None:
        rows = rows.filter(ReturnDeliveryNote.id != exclude_rdn_id)
    rows = rows.all()

    return {
        _make_batch_key(row.product_id, row.batch_no): float(row.qty or 0)
        for row in rows
    }


def _validate_rdn_batch_limits(
    db: Session,
    *,
    invoice_id: UUID,
    items,
    pending_by_batch: dict[str, float],
) -> dict[str, float]:
    invoice_qty_by_batch = _invoice_batch_quantities(db, invoice_id)
    requested_by_batch: dict[str, float] = {}
    invoice_qty_by_item_id: dict[str, float] = {}

    for item in items:
        invoice_item = (
            db.query(SalesInvoiceItem)
            .filter(
                SalesInvoiceItem.id == item.invoice_item_id,
                SalesInvoiceItem.invoice_id == invoice_id,
                SalesInvoiceItem.is_deleted == False,
            )
            .first()
        )
        if not invoice_item:
            raise HTTPException(status_code=400, detail="Invoice item not found")
        if invoice_item.product_id != item.product_id:
            raise HTTPException(status_code=400, detail="Product does not match invoice item")

        invoice_qty_by_item_id[str(invoice_item.id)] = float(invoice_item.quantity or 0)

        invoice_batch_no = (invoice_item.batch_no or "").strip()
        item_batch_no = (getattr(item, "batch_no", None) or "").strip()
        if invoice_batch_no and item_batch_no and invoice_batch_no != item_batch_no:
            raise HTTPException(status_code=400, detail="Batch does not match invoice item")

        batch_no = invoice_batch_no or item_batch_no
        key = _make_batch_key(item.product_id, batch_no)
        invoice_qty = invoice_qty_by_batch.get(key)
        if invoice_qty is None:
            raise HTTPException(status_code=400, detail="Invoice item not found")

        next_requested = requested_by_batch.get(key, 0.0) + float(item.return_quantity or 0)
        requested_by_batch[key] = next_requested

        pending = pending_by_batch.get(key, 0.0)
        if next_requested + pending > invoice_qty + 1e-6:
            raise HTTPException(
                status_code=400,
                detail="Total return quantity exceeds invoiced quantity for this product/batch",
            )

    return invoice_qty_by_item_id


def _compute_invoice_status(amount_paid: int, total_amount: int) -> str:
    if amount_paid <= 0:
        return "issued"
    if amount_paid >= total_amount:
        return "paid"
    return "partial_paid"


def _apply_credit_note_to_invoice(invoice: SalesInvoice, totals: dict[str, int]) -> None:
    original_total = int(invoice.total_amount or 0)
    invoice.subtotal = max(0, int(invoice.subtotal or 0) - totals["subtotal"])
    invoice.total_discount = max(0, int(invoice.total_discount or 0) - totals["total_discount"])
    invoice.total_taxable_amount = max(0, int(invoice.total_taxable_amount or 0) - totals["total_taxable"])
    invoice.total_cgst = max(0, int(invoice.total_cgst or 0) - totals["total_cgst"])
    invoice.total_sgst = max(0, int(invoice.total_sgst or 0) - totals["total_sgst"])
    invoice.total_igst = max(0, int(invoice.total_igst or 0) - totals["total_igst"])
    invoice.total_gst = max(0, int(invoice.total_cgst or 0) + int(invoice.total_sgst or 0) + int(invoice.total_igst or 0))
    exact_total = int(invoice.total_taxable_amount or 0) + int(invoice.total_gst or 0)
    invoice.total_amount = round_paise_to_nearest_5(exact_total)
    invoice.amount_due = max(0, int(invoice.total_amount or 0) - int(invoice.amount_paid or 0))
    if original_total > 0 and int(invoice.total_amount or 0) == 0:
        invoice.status = "returned"
    else:
        invoice.status = _compute_invoice_status(int(invoice.amount_paid or 0), int(invoice.total_amount or 0))


def _create_credit_note_for_rdn(
    db: Session,
    *,
    rdn: ReturnDeliveryNote,
    items: list[ReturnDeliveryNoteItem],
    invoice: SalesInvoice,
    current_user: User,
) -> tuple[RdnCreditNote, dict[str, int]]:
    existing = (
        db.query(RdnCreditNote)
        .filter(RdnCreditNote.rdn_id == rdn.id, RdnCreditNote.is_deleted == False)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Credit note already exists for this RDN")

    if invoice.status not in {"issued", "partial_paid", "paid"}:
        raise HTTPException(status_code=400, detail="Invoice must be posted before creating credit note")

    tax_mode = invoice_type_tax_mode(invoice.invoice_type, fallback_is_igst=bool(invoice.is_igst))
    gst_applicable = tax_mode["gst_applicable"]
    is_igst = tax_mode["is_igst"]

    credit_note = RdnCreditNote(
        credit_note_number=rdn.rdn_number,
        rdn_id=rdn.id,
        sales_invoice_id=rdn.sales_invoice_id,
        customer_id=rdn.customer_id,
        credit_note_date=rdn.receipt_date,
        status="posted",
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(credit_note)
    db.flush()

    totals = {
        "subtotal": 0,
        "total_discount": 0,
        "total_taxable": 0,
        "total_cgst": 0,
        "total_sgst": 0,
        "total_igst": 0,
    }

    for item in items:
        invoice_item = (
            db.query(SalesInvoiceItem)
            .filter(SalesInvoiceItem.id == item.invoice_item_id, SalesInvoiceItem.is_deleted == False)
            .first()
        )
        if not invoice_item or invoice_item.invoice_id != invoice.id:
            raise HTTPException(status_code=400, detail="Invoice item not found for credit note")

        return_qty = float(item.return_quantity or 0)
        if return_qty <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be greater than zero")
        if return_qty > float(invoice_item.quantity or 0) + 1e-6:
            raise HTTPException(status_code=400, detail="Return quantity exceeds invoice quantity")

        discount_percent = float(invoice_item.discount_percent or 0)
        calc = calc_line_item(
            return_qty,
            int(invoice_item.unit_price or 0),
            discount_percent,
            int(invoice_item.gst_rate or 0),
            is_igst,
            gst_applicable,
        )

        db.add(
            RdnCreditNoteItem(
                credit_note_id=credit_note.id,
                product_id=item.product_id,
                invoice_item_id=item.invoice_item_id,
                return_quantity=return_qty,
                unit_price=int(invoice_item.unit_price or 0),
                mrp=invoice_item.mrp if invoice_item.mrp is not None else item.mrp,
                discount_percent=discount_percent,
                discount_amount=calc["discount"],
                taxable_amount=calc["taxable"],
                gst_rate=calc["gst_rate"],
                cgst_amount=calc["cgst"],
                sgst_amount=calc["sgst"],
                igst_amount=calc["igst"],
                total_amount=calc["total"],
            )
        )

        totals["subtotal"] += calc["gross"]
        totals["total_discount"] += calc["discount"]
        totals["total_taxable"] += calc["taxable"]
        totals["total_cgst"] += calc["cgst"]
        totals["total_sgst"] += calc["sgst"]
        totals["total_igst"] += calc["igst"]

    credit_note.subtotal = totals["subtotal"]
    credit_note.total_discount = totals["total_discount"]
    credit_note.total_taxable_amount = totals["total_taxable"]
    credit_note.total_cgst = totals["total_cgst"]
    credit_note.total_sgst = totals["total_sgst"]
    credit_note.total_igst = totals["total_igst"]
    credit_note.total_gst = totals["total_cgst"] + totals["total_sgst"] + totals["total_igst"]
    exact_total = credit_note.total_taxable_amount + credit_note.total_gst
    credit_note.total_amount = round_paise_to_nearest_5(exact_total)

    return credit_note, totals


@router.get("/api/v1/rdn", response_model=RDNOverviewResponse)
async def list_rdns(
    search: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_read")),
):
    search = normalize_search_query(search)
    query = (
        db.query(ReturnDeliveryNote, ReturnDeliveryNoteItem, Product, Customer, SalesInvoice)
        .join(ReturnDeliveryNoteItem, ReturnDeliveryNoteItem.rdn_id == ReturnDeliveryNote.id)
        .join(Product, ReturnDeliveryNoteItem.product_id == Product.id)
        .join(Customer, ReturnDeliveryNote.customer_id == Customer.id)
        .join(SalesInvoice, ReturnDeliveryNote.sales_invoice_id == SalesInvoice.id)
        .filter(
            ReturnDeliveryNote.is_deleted == False,
            ReturnDeliveryNoteItem.is_deleted == False,
        )
    )
    query = _scope_to_owner(query, ReturnDeliveryNote, current_user)

    if status:
        query = query.filter(ReturnDeliveryNote.status == status)
    if search:
        like_text = f"%{search}%"
        query = query.filter(ReturnDeliveryNote.rdn_number.ilike(like_text))

    total = query.count()
    rows = (
        query.order_by(ReturnDeliveryNote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for rdn, rdn_item, product, customer, invoice in rows:
        items.append(
            {
                "rdn_id": rdn.id,
                "rdn_number": rdn.rdn_number,
                "customer_id": rdn.customer_id,
                "customer_name": customer.company_name,
                "sales_invoice_id": rdn.sales_invoice_id,
                "invoice_number": invoice.invoice_number,
                "receipt_date": rdn.receipt_date,
                "product_id": rdn_item.product_id,
                "product_code": product.product_code,
                "product_name": product.name,
                "return_quantity": float(rdn_item.return_quantity or 0),
                "mrp": rdn_item.mrp,
                "status": rdn.status,
            }
        )

    return RDNOverviewResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/api/v1/rdn/customization-options")
async def rdn_customization_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_read")),
):
    rows = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.company_id == current_user.company_id,
            CustomizationOption.module == "rdn",
            CustomizationOption.field_name == "return_reason",
            CustomizationOption.is_active == True,
            CustomizationOption.is_deleted == False,
        )
        .order_by(CustomizationOption.sort_order.asc(), CustomizationOption.option_value.asc())
        .all()
    )
    options = [
        {"value": row.option_value, "label": row.display_label or row.option_value}
        for row in rows
    ]
    return {"return_reasons": options}


@router.get("/api/v1/rdn/credit-notes", response_model=RDNCreditNoteOverviewResponse)
async def list_rdn_credit_notes(
    search: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_read")),
):
    search = normalize_search_query(search)
    query = (
        db.query(RdnCreditNote, RdnCreditNoteItem, Product, Customer, SalesInvoice)
        .join(RdnCreditNoteItem, RdnCreditNoteItem.credit_note_id == RdnCreditNote.id)
        .join(Product, RdnCreditNoteItem.product_id == Product.id)
        .join(Customer, RdnCreditNote.customer_id == Customer.id)
        .join(SalesInvoice, RdnCreditNote.sales_invoice_id == SalesInvoice.id)
        .filter(
            RdnCreditNote.is_deleted == False,
            RdnCreditNoteItem.is_deleted == False,
        )
    )
    query = _scope_to_owner(query, RdnCreditNote, current_user)

    if status:
        query = query.filter(RdnCreditNote.status == status)
    if search:
        like_text = f"%{search}%"
        query = query.filter(
            or_(
                RdnCreditNote.credit_note_number.ilike(like_text),
                SalesInvoice.invoice_number.ilike(like_text),
            )
        )

    total = query.count()
    rows = (
        query.order_by(RdnCreditNote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for credit_note, note_item, product, customer, invoice in rows:
        items.append(
            {
                "credit_note_id": credit_note.id,
                "credit_note_number": credit_note.credit_note_number,
                "rdn_id": credit_note.rdn_id,
                "sales_invoice_id": credit_note.sales_invoice_id,
                "invoice_number": invoice.invoice_number,
                "customer_id": credit_note.customer_id,
                "customer_name": customer.company_name,
                "credit_note_date": credit_note.credit_note_date,
                "product_id": note_item.product_id,
                "product_code": product.product_code,
                "product_name": product.name,
                "mrp": note_item.mrp,
                "gst_rate": note_item.gst_rate,
                "status": credit_note.status,
            }
        )

    return RDNCreditNoteOverviewResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/api/v1/rdn/credit-notes/{credit_note_id}", response_model=RDNCreditNoteDetailResponse)
async def get_rdn_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_read")),
):
    credit_note = (
        db.query(RdnCreditNote)
        .filter(RdnCreditNote.id == credit_note_id, RdnCreditNote.is_deleted == False)
        .first()
    )
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    _enforce_owner(credit_note, current_user)

    rdn = (
        db.query(ReturnDeliveryNote)
        .filter(ReturnDeliveryNote.id == credit_note.rdn_id, ReturnDeliveryNote.is_deleted == False)
        .first()
    )
    invoice = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id == credit_note.sales_invoice_id, SalesInvoice.is_deleted == False)
        .first()
    )
    customer = (
        db.query(Customer)
        .filter(Customer.id == credit_note.customer_id, Customer.is_deleted == False)
        .first()
    )

    if invoice:
        _enforce_owner(invoice, current_user)
    if customer:
        _enforce_owner(customer, current_user)
    if rdn:
        _enforce_owner(rdn, current_user)

    rows = (
        db.query(RdnCreditNoteItem, Product)
        .join(Product, RdnCreditNoteItem.product_id == Product.id)
        .filter(RdnCreditNoteItem.credit_note_id == credit_note.id, RdnCreditNoteItem.is_deleted == False)
        .all()
    )

    items = []
    for note_item, product in rows:
        items.append(
            {
                "id": note_item.id,
                "credit_note_id": note_item.credit_note_id,
                "product_id": note_item.product_id,
                "product_code": product.product_code,
                "product_name": product.name,
                "invoice_item_id": note_item.invoice_item_id,
                "return_quantity": float(note_item.return_quantity or 0),
                "unit_price": note_item.unit_price,
                "mrp": note_item.mrp,
                "discount_percent": float(note_item.discount_percent or 0),
                "discount_amount": note_item.discount_amount,
                "taxable_amount": note_item.taxable_amount,
                "gst_rate": note_item.gst_rate,
                "cgst_amount": note_item.cgst_amount,
                "sgst_amount": note_item.sgst_amount,
                "igst_amount": note_item.igst_amount,
                "total_amount": note_item.total_amount,
            }
        )

    detail = RDNCreditNoteResponse.model_validate(credit_note)
    detail.invoice_number = invoice.invoice_number if invoice else None
    detail.invoice_date = invoice.invoice_date if invoice else None
    detail.customer_name = customer.company_name if customer else None
    detail.rdn_created_at = rdn.created_at if rdn else None

    return {
        "credit_note": detail,
        "items": items,
    }


@router.post("/api/v1/rdn", response_model=RDNResponse, status_code=201)
async def create_rdn(
    payload: RDNCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_write")),
):
    invoice = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id == payload.sales_invoice_id, SalesInvoice.is_deleted == False)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=400, detail="Invalid invoice")
    _enforce_owner(invoice, current_user)

    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.is_deleted == False)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)

    if invoice.customer_id != payload.customer_id:
        raise HTTPException(status_code=400, detail="Invoice does not belong to customer")

    reason_map = _load_return_reason_map(db, current_user.company_id)
    if not reason_map:
        raise HTTPException(status_code=400, detail="Return reasons are not configured")

    for item in payload.items:
        if item.reason_code not in reason_map:
            raise HTTPException(status_code=400, detail="Invalid return reason")
        if item.return_quantity <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be greater than zero")
        if not item.invoice_item_id:
            raise HTTPException(status_code=400, detail="Invoice item is required")

    pending_by_batch = _pending_invoice_batch_quantities(db, payload.sales_invoice_id)
    invoice_qty_by_item_id = _validate_rdn_batch_limits(
        db,
        invoice_id=payload.sales_invoice_id,
        items=payload.items,
        pending_by_batch=pending_by_batch,
    )

    rdn = ReturnDeliveryNote(
        rdn_number=generate_rdn_number(db, current_user.company_id),
        customer_id=payload.customer_id,
        sales_invoice_id=payload.sales_invoice_id,
        customer_delivery_number=payload.customer_delivery_number,
        customer_delivery_date=payload.customer_delivery_date,
        receipt_date=payload.receipt_date,
        status="draft",
        notes=payload.notes,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(rdn)
    db.flush()

    for item in payload.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id, Product.is_deleted == False)
            .first()
        )
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)

        db.add(
            ReturnDeliveryNoteItem(
                rdn_id=rdn.id,
                product_id=item.product_id,
                invoice_item_id=item.invoice_item_id,
                batch_no=item.batch_no,
                manufacture_date=item.manufacture_date,
                expiry_date=item.expiry_date,
                invoice_quantity=float(invoice_qty_by_item_id.get(str(item.invoice_item_id)) or 0),
                return_quantity=item.return_quantity,
                mrp=product.mrp,
                reason_code=item.reason_code,
                reason_label=reason_map[item.reason_code],
            )
        )

    log_audit_event(
        db,
        action="CREATE_RDN",
        resource_type="rdn",
        status="success",
        user_id=current_user.id,
        resource_id=rdn.id,
        details={
            "rdn_number": rdn.rdn_number,
            "invoice_id": str(rdn.sales_invoice_id),
            "customer_id": str(rdn.customer_id),
        },
    )

    db.commit()
    db.refresh(rdn)
    return RDNResponse.model_validate(rdn)


@router.get("/api/v1/rdn/{rdn_id}")
async def get_rdn(
    rdn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_read")),
):
    rdn = (
        db.query(ReturnDeliveryNote)
        .filter(
            ReturnDeliveryNote.id == rdn_id,
            ReturnDeliveryNote.is_deleted == False,
        )
        .with_for_update()
        .first()
    )
    if not rdn:
        raise HTTPException(status_code=404, detail="RDN not found")
    _enforce_owner(rdn, current_user)

    rows = (
        db.query(ReturnDeliveryNoteItem, Product)
        .join(Product, ReturnDeliveryNoteItem.product_id == Product.id)
        .filter(ReturnDeliveryNoteItem.rdn_id == rdn_id, ReturnDeliveryNoteItem.is_deleted == False)
        .all()
    )

    items = []
    for rdn_item, product in rows:
        items.append(
            {
                "id": rdn_item.id,
                "rdn_id": rdn_item.rdn_id,
                "product_id": rdn_item.product_id,
                "product_code": product.product_code,
                "product_name": product.name,
                "invoice_item_id": rdn_item.invoice_item_id,
                "batch_no": rdn_item.batch_no,
                "manufacture_date": rdn_item.manufacture_date,
                "expiry_date": rdn_item.expiry_date,
                "invoice_quantity": float(rdn_item.invoice_quantity or 0),
                "return_quantity": float(rdn_item.return_quantity or 0),
                "mrp": rdn_item.mrp,
                "reason_code": rdn_item.reason_code,
                "reason_label": rdn_item.reason_label,
            }
        )

    return {
        "rdn": RDNResponse.model_validate(rdn),
        "items": items,
    }


@router.put("/api/v1/rdn/{rdn_id}", response_model=RDNResponse)
async def update_rdn(
    rdn_id: UUID,
    payload: RDNUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_write")),
):
    rdn = db.query(ReturnDeliveryNote).filter(
        ReturnDeliveryNote.id == rdn_id,
        ReturnDeliveryNote.is_deleted == False,
    ).first()
    if not rdn:
        raise HTTPException(status_code=404, detail="RDN not found")
    _enforce_owner(rdn, current_user)

    if rdn.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft RDN can be updated")

    if payload.sales_invoice_id != rdn.sales_invoice_id:
        raise HTTPException(status_code=400, detail="Invoice change not allowed")
    if payload.customer_id != rdn.customer_id:
        raise HTTPException(status_code=400, detail="Customer change not allowed")

    reason_map = _load_return_reason_map(db, current_user.company_id)
    if not reason_map:
        raise HTTPException(status_code=400, detail="Return reasons are not configured")

    rdn.customer_delivery_number = payload.customer_delivery_number
    rdn.customer_delivery_date = payload.customer_delivery_date
    rdn.receipt_date = payload.receipt_date
    rdn.notes = payload.notes

    for item in payload.items:
        if item.reason_code not in reason_map:
            raise HTTPException(status_code=400, detail="Invalid return reason")
        if item.return_quantity <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be greater than zero")
        if not item.invoice_item_id:
            raise HTTPException(status_code=400, detail="Invoice item is required")

    pending_by_batch = _pending_invoice_batch_quantities(
        db,
        payload.sales_invoice_id,
        exclude_rdn_id=rdn.id,
    )
    invoice_qty_by_item_id = _validate_rdn_batch_limits(
        db,
        invoice_id=payload.sales_invoice_id,
        items=payload.items,
        pending_by_batch=pending_by_batch,
    )

    db.query(ReturnDeliveryNoteItem).filter(ReturnDeliveryNoteItem.rdn_id == rdn.id).update(
        {"is_deleted": True, "deleted_at": datetime.utcnow()}
    )

    for item in payload.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id, Product.is_deleted == False)
            .first()
        )
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)

        db.add(
            ReturnDeliveryNoteItem(
                rdn_id=rdn.id,
                product_id=item.product_id,
                invoice_item_id=item.invoice_item_id,
                batch_no=item.batch_no,
                manufacture_date=item.manufacture_date,
                expiry_date=item.expiry_date,
                invoice_quantity=float(invoice_qty_by_item_id.get(str(item.invoice_item_id)) or 0),
                return_quantity=item.return_quantity,
                mrp=product.mrp,
                reason_code=item.reason_code,
                reason_label=reason_map[item.reason_code],
            )
        )

    log_audit_event(
        db,
        action="UPDATE_RDN",
        resource_type="rdn",
        status="success",
        user_id=current_user.id,
        resource_id=rdn.id,
        details={
            "rdn_number": rdn.rdn_number,
            "invoice_id": str(rdn.sales_invoice_id),
            "customer_id": str(rdn.customer_id),
        },
    )

    db.commit()
    db.refresh(rdn)
    return RDNResponse.model_validate(rdn)


@router.post("/api/v1/rdn/{rdn_id}/confirm", response_model=RDNResponse)
async def confirm_rdn(
    rdn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rdn = db.query(ReturnDeliveryNote).filter(
        ReturnDeliveryNote.id == rdn_id,
        ReturnDeliveryNote.is_deleted == False,
    ).first()
    if not rdn:
        raise HTTPException(status_code=404, detail="RDN not found")
    _enforce_owner(rdn, current_user)

    if rdn.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft RDN can be confirmed")

    items = (
        db.query(ReturnDeliveryNoteItem)
        .filter(ReturnDeliveryNoteItem.rdn_id == rdn.id, ReturnDeliveryNoteItem.is_deleted == False)
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="No items to confirm")

    pending_by_batch = _pending_invoice_batch_quantities(
        db,
        rdn.sales_invoice_id,
        exclude_rdn_id=rdn.id,
    )
    _validate_rdn_batch_limits(
        db,
        invoice_id=rdn.sales_invoice_id,
        items=items,
        pending_by_batch=pending_by_batch,
    )

    invoice = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id == rdn.sales_invoice_id, SalesInvoice.is_deleted == False)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=400, detail="Invoice not found for credit note")

    _enforce_owner(invoice, current_user)
    issued_stock = (
        db.query(StockLedger.id)
        .filter(
            StockLedger.reference_type == "invoice",
            StockLedger.reference_id == invoice.id,
            StockLedger.transaction_type == "sale",
            StockLedger.is_deleted == False,
        )
        .first()
    )
    if not issued_stock:
        raise HTTPException(status_code=400, detail="Issue invoice before confirming RDN")

    sold_rows = (
        db.query(
            StockLedger.product_id,
            func.coalesce(func.sum(StockLedger.quantity), 0).label("qty"),
        )
        .filter(
            StockLedger.reference_type == "invoice",
            StockLedger.reference_id == invoice.id,
            StockLedger.transaction_type == "sale",
            StockLedger.is_deleted == False,
        )
        .group_by(StockLedger.product_id)
        .all()
    )
    sold_by_product = {
        row.product_id: abs(float(row.qty or 0))
        for row in sold_rows
    }

    returned_rows = (
        db.query(
            StockLedger.product_id,
            func.coalesce(func.sum(StockLedger.quantity), 0).label("qty"),
        )
        .join(ReturnDeliveryNote, StockLedger.reference_id == ReturnDeliveryNote.id)
        .filter(
            StockLedger.reference_type == "rdn",
            StockLedger.transaction_type == "sale_return",
            StockLedger.is_deleted == False,
            ReturnDeliveryNote.sales_invoice_id == invoice.id,
            ReturnDeliveryNote.is_deleted == False,
        )
        .group_by(StockLedger.product_id)
        .all()
    )
    returned_by_product = {
        row.product_id: float(row.qty or 0)
        for row in returned_rows
    }

    for item in items:
        sold_qty = float(sold_by_product.get(item.product_id, 0.0))
        if sold_qty <= 0:
            raise HTTPException(status_code=400, detail="Issue invoice before confirming RDN")
        already_returned = float(returned_by_product.get(item.product_id, 0.0))
        next_return = already_returned + float(item.return_quantity or 0)
        if next_return > sold_qty + 1e-6:
            raise HTTPException(
                status_code=400,
                detail="Return quantity exceeds issued quantity for this product",
            )

    existing_rdn_stock = (
        db.query(StockLedger.id)
        .filter(
            StockLedger.reference_type == "rdn",
            StockLedger.reference_id == rdn.id,
            StockLedger.is_deleted == False,
        )
        .first()
    )
    if existing_rdn_stock:
        raise HTTPException(status_code=400, detail="Stock already updated for this RDN")

    for item in items:
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="sale_return",
            reference_type="rdn",
            reference_id=rdn.id,
            reference_number=rdn.rdn_number,
            quantity=float(item.return_quantity),
            rate=int(item.mrp or 0),
            transaction_date=rdn.receipt_date,
            created_by=current_user.id,
        )

    refresh_materialized_view(db)
    credit_note, totals = _create_credit_note_for_rdn(
        db,
        rdn=rdn,
        items=items,
        invoice=invoice,
        current_user=current_user,
    )
    _apply_credit_note_to_invoice(invoice, totals)

    log_audit_event(
        db,
        action="CREATE_RDN_CREDIT_NOTE",
        resource_type="rdn",
        status="success",
        user_id=current_user.id,
        resource_id=credit_note.id,
        details={
            "rdn_number": rdn.rdn_number,
            "credit_note_number": credit_note.credit_note_number,
            "invoice_id": str(rdn.sales_invoice_id),
            "invoice_number": invoice.invoice_number,
            "customer_id": str(rdn.customer_id),
        },
    )

    rdn.status = "confirmed"
    rdn.confirmed_by = current_user.id
    rdn.confirmed_at = datetime.utcnow()

    log_audit_event(
        db,
        action="CONFIRM_RDN",
        resource_type="rdn",
        status="success",
        user_id=current_user.id,
        resource_id=rdn.id,
        details={
            "rdn_number": rdn.rdn_number,
            "invoice_id": str(rdn.sales_invoice_id),
            "customer_id": str(rdn.customer_id),
        },
    )

    log_audit_event(
        db,
        action="CREATE_RDN_CREDIT_NOTE",
        resource_type="rdn-credit-note",
        status="success",
        user_id=current_user.id,
        resource_id=credit_note.id,
        details={
            "credit_note_number": credit_note.credit_note_number,
            "rdn_id": str(rdn.id),
            "invoice_id": str(rdn.sales_invoice_id),
            "customer_id": str(rdn.customer_id),
        },
    )

    db.commit()
    db.refresh(rdn)
    return RDNResponse.model_validate(rdn)


@router.post("/api/v1/rdn/{rdn_id}/cancel", response_model=RDNResponse)
async def cancel_rdn(
    rdn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("rdn_write")),
):
    rdn = db.query(ReturnDeliveryNote).filter(
        ReturnDeliveryNote.id == rdn_id,
        ReturnDeliveryNote.is_deleted == False,
    ).first()
    if not rdn:
        raise HTTPException(status_code=404, detail="RDN not found")
    _enforce_owner(rdn, current_user)

    if rdn.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft RDN can be cancelled")

    rdn.status = "cancelled"
    rdn.cancelled_by = current_user.id
    rdn.cancelled_at = datetime.utcnow()

    log_audit_event(
        db,
        action="CANCEL_RDN",
        resource_type="rdn",
        status="success",
        user_id=current_user.id,
        resource_id=rdn.id,
        details={
            "rdn_number": rdn.rdn_number,
            "invoice_id": str(rdn.sales_invoice_id),
            "customer_id": str(rdn.customer_id),
        },
    )

    db.commit()
    db.refresh(rdn)
    return RDNResponse.model_validate(rdn)



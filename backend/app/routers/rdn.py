"""Return Delivery Note (RDN) endpoints."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions, require_role, scope_query_to_company
from app.models.customization_option import CustomizationOption
from app.models.customer import Customer
from app.models.product import Product
from app.models.rdn import ReturnDeliveryNote, ReturnDeliveryNoteItem
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.models.user import User
from app.schemas.rdn import (
    RDNCreateRequest,
    RDNOverviewResponse,
    RDNResponse,
    RDNUpdateRequest,
)
from app.services.audit_service import log_audit_event
from app.services.auth_service import normalize_role
from app.services.order_number_service import generate_rdn_number
from app.services.stock_service import add_stock_entry, refresh_materialized_view
from app.utils.input_validation import normalize_search_query

router = APIRouter(tags=["rdn"])


def _scope_to_owner(query, model_cls, current_user: User):
    if current_user.company_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a company")
    query = scope_query_to_company(query, model_cls, current_user.company_id)
    if normalize_role(current_user.role) in {"admin", "inventory manager", "general manager"}:
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


def _load_return_reason_map(db: Session) -> dict[str, str]:
    rows = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.module == "rdn",
            CustomizationOption.field_name == "return_reason",
            CustomizationOption.is_active == True,
            CustomizationOption.is_deleted == False,
        )
        .order_by(CustomizationOption.sort_order.asc(), CustomizationOption.option_value.asc())
        .all()
    )
    return {row.option_value: (row.display_label or row.option_value) for row in rows}


def _pending_invoice_quantities(
    db: Session,
    invoice_id: UUID,
    *,
    exclude_rdn_id: UUID | None = None,
) -> dict[str, float]:
    items = (
        db.query(ReturnDeliveryNoteItem)
        .join(ReturnDeliveryNote, ReturnDeliveryNoteItem.rdn_id == ReturnDeliveryNote.id)
        .filter(
            ReturnDeliveryNote.sales_invoice_id == invoice_id,
            ReturnDeliveryNote.status.in_(["draft", "confirmed"]),
            ReturnDeliveryNote.is_deleted == False,
            ReturnDeliveryNoteItem.is_deleted == False,
        )
    )
    if exclude_rdn_id is not None:
        items = items.filter(ReturnDeliveryNote.id != exclude_rdn_id)
    items = items.all()

    pending: dict[str, float] = {}
    for item in items:
        key = str(item.invoice_item_id) if item.invoice_item_id else ""
        if not key:
            continue
        pending[key] = pending.get(key, 0.0) + float(item.return_quantity or 0)
    return pending


def _validate_invoice_item_quantities(
    db: Session,
    *,
    invoice_id: UUID,
    invoice_item_id: UUID,
    return_quantity: float,
    pending_by_item: dict[str, float],
) -> float:
    invoice_item = (
        db.query(SalesInvoiceItem)
        .filter(
            SalesInvoiceItem.id == invoice_item_id,
            SalesInvoiceItem.invoice_id == invoice_id,
            SalesInvoiceItem.is_deleted == False,
        )
        .first()
    )
    if not invoice_item:
        raise HTTPException(status_code=400, detail="Invoice item not found")

    invoiced_qty = float(invoice_item.quantity or 0)
    pending = pending_by_item.get(str(invoice_item_id), 0.0)
    remaining = invoiced_qty - pending
    if return_quantity > remaining + 1e-6:
        raise HTTPException(status_code=400, detail="Return quantity exceeds invoice quantity")

    return invoiced_qty


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

    reason_map = _load_return_reason_map(db)
    if not reason_map:
        raise HTTPException(status_code=400, detail="Return reasons are not configured")

    pending_by_item = _pending_invoice_quantities(db, payload.sales_invoice_id)

    rdn = ReturnDeliveryNote(
        rdn_number=generate_rdn_number(db),
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
        if item.reason_code not in reason_map:
            raise HTTPException(status_code=400, detail="Invalid return reason")
        if item.return_quantity <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be greater than zero")
        if not item.invoice_item_id:
            raise HTTPException(status_code=400, detail="Invoice item is required")

        invoice_qty = _validate_invoice_item_quantities(
            db,
            invoice_id=payload.sales_invoice_id,
            invoice_item_id=item.invoice_item_id,
            return_quantity=item.return_quantity,
            pending_by_item=pending_by_item,
        )

        invoice_item = (
            db.query(SalesInvoiceItem)
            .filter(SalesInvoiceItem.id == item.invoice_item_id)
            .first()
        )
        if invoice_item and invoice_item.product_id != item.product_id:
            raise HTTPException(status_code=400, detail="Product does not match invoice item")

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
                invoice_quantity=float(invoice_qty or 0),
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
    rdn = db.query(ReturnDeliveryNote).filter(
        ReturnDeliveryNote.id == rdn_id,
        ReturnDeliveryNote.is_deleted == False,
    ).first()
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

    reason_map = _load_return_reason_map(db)
    if not reason_map:
        raise HTTPException(status_code=400, detail="Return reasons are not configured")

    rdn.customer_delivery_number = payload.customer_delivery_number
    rdn.customer_delivery_date = payload.customer_delivery_date
    rdn.receipt_date = payload.receipt_date
    rdn.notes = payload.notes

    pending_by_item = _pending_invoice_quantities(
        db,
        payload.sales_invoice_id,
        exclude_rdn_id=rdn.id,
    )

    db.query(ReturnDeliveryNoteItem).filter(ReturnDeliveryNoteItem.rdn_id == rdn.id).update(
        {"is_deleted": True, "deleted_at": datetime.utcnow()}
    )

    for item in payload.items:
        if item.reason_code not in reason_map:
            raise HTTPException(status_code=400, detail="Invalid return reason")
        if item.return_quantity <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be greater than zero")
        if not item.invoice_item_id:
            raise HTTPException(status_code=400, detail="Invoice item is required")

        invoice_qty = _validate_invoice_item_quantities(
            db,
            invoice_id=payload.sales_invoice_id,
            invoice_item_id=item.invoice_item_id,
            return_quantity=item.return_quantity,
            pending_by_item=pending_by_item,
        )

        invoice_item = (
            db.query(SalesInvoiceItem)
            .filter(SalesInvoiceItem.id == item.invoice_item_id)
            .first()
        )
        if invoice_item and invoice_item.product_id != item.product_id:
            raise HTTPException(status_code=400, detail="Product does not match invoice item")

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
                invoice_quantity=float(invoice_qty or 0),
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

"""Customer master router."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerResponse,
    CustomersListResponse,
    CustomerBalanceResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _generate_customer_code(db: Session) -> str:
    count = db.query(Customer).count()
    return f"CUST-{str(count + 1).zfill(5)}"


def _apply_gstin_state_code(payload: CustomerCreateRequest | CustomerUpdateRequest) -> None:
    if payload.gstin and len(payload.gstin) >= 2:
        gst_state_code = payload.gstin[:2]
        if not payload.billing_state_code:
            payload.billing_state_code = gst_state_code


def _normalize_shipping(payload: CustomerCreateRequest | CustomerUpdateRequest) -> None:
    if payload.same_as_billing:
        payload.shipping_address_line1 = payload.billing_address_line1
        payload.shipping_address_line2 = payload.billing_address_line2
        payload.shipping_city = payload.billing_city
        payload.shipping_state = payload.billing_state
        payload.shipping_state_code = payload.billing_state_code
        payload.shipping_pincode = payload.billing_pincode


def _customer_balance(db: Session, customer_id: UUID) -> CustomerBalanceResponse:
    """Calculate customer balance from issued invoices and cleared payments.
    
    BUG-09 fix: Only count payments with status='cleared' (not bounced/cancelled).
    BUG-21 fix: Explicit try/except with logging note.
    """
    try:
        invoiced = db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM sales_invoices "
                "WHERE customer_id = :customer_id AND is_deleted = FALSE "
                "AND status NOT IN ('draft', 'cancelled')"
            ),
            {"customer_id": str(customer_id)},
        ).scalar_one()
        paid = db.execute(
            text(
                "SELECT COALESCE(SUM(amount), 0) FROM payments "
                "WHERE customer_id = :customer_id AND payment_type = 'receipt' "
                "AND status = 'cleared' AND is_deleted = FALSE"
            ),
            {"customer_id": str(customer_id)},
        ).scalar_one()
    except SQLAlchemyError:
        # Tables may not exist yet during initial setup
        invoiced = 0
        paid = 0

    return CustomerBalanceResponse(
        total_invoiced=int(invoiced or 0),
        total_paid=int(paid or 0),
        balance_due=int((invoiced or 0) - (paid or 0)),
    )


@router.get("", response_model=CustomersListResponse)
async def list_customers(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_read")),
):
    query = db.query(Customer).filter(Customer.is_deleted == False)

    if search:
        like_text = f"%{search}%"
        query = query.filter(
            or_(
                Customer.customer_code.ilike(like_text),
                Customer.company_name.ilike(like_text),
                Customer.phone.ilike(like_text),
            )
        )

    if is_active is not None:
        query = query.filter(Customer.is_active == is_active)

    total = query.count()
    items = (
        query.order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CustomersListResponse(
        items=[CustomerResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    payload: CustomerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_write")),
):
    if payload.gstin:
        duplicate = db.query(Customer).filter(Customer.gstin == payload.gstin, Customer.is_deleted == False).first()
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "DUPLICATE_GSTIN", "message": "GSTIN already exists"},
            )

    _apply_gstin_state_code(payload)
    _normalize_shipping(payload)

    customer = Customer(
        **payload.model_dump(exclude={"customer_code"}),
        customer_code=payload.customer_code or _generate_customer_code(db),
        created_by=current_user.id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_read")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_write")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if payload.gstin:
        duplicate = (
            db.query(Customer)
            .filter(Customer.gstin == payload.gstin, Customer.id != customer_id, Customer.is_deleted == False)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "DUPLICATE_GSTIN", "message": "GSTIN already exists"},
            )

    _apply_gstin_state_code(payload)
    _normalize_shipping(payload)

    for field, value in payload.model_dump(exclude={"customer_code"}).items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_write")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    balance = _customer_balance(db, customer.id)
    if balance.balance_due > 0:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "OUTSTANDING_EXISTS", "message": "Customer has outstanding balance"},
        )

    customer.is_deleted = True
    customer.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "Customer deleted"}


@router.get("/{customer_id}/ledger")
async def customer_ledger(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_read")),
):
    """BUG-10 fix: Return actual transaction history for the customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Fetch invoices
    try:
        invoices = db.execute(
            text(
                "SELECT id, invoice_number AS reference, invoice_date AS date, "
                "'invoice' AS type, total_amount AS debit, 0 AS credit, status "
                "FROM sales_invoices WHERE customer_id = :cid AND is_deleted = FALSE "
                "AND status NOT IN ('draft', 'cancelled') "
                "ORDER BY invoice_date DESC"
            ),
            {"cid": str(customer_id)},
        ).mappings().all()
    except SQLAlchemyError:
        invoices = []

    # Fetch receipts (cleared payments)
    try:
        receipts = db.execute(
            text(
                "SELECT id, payment_number AS reference, payment_date AS date, "
                "'receipt' AS type, 0 AS debit, amount AS credit, status "
                "FROM payments WHERE customer_id = :cid AND payment_type = 'receipt' "
                "AND status = 'cleared' AND is_deleted = FALSE "
                "ORDER BY payment_date DESC"
            ),
            {"cid": str(customer_id)},
        ).mappings().all()
    except SQLAlchemyError:
        receipts = []

    # Fetch sales returns (confirmed)
    try:
        returns = db.execute(
            text(
                "SELECT id, return_number AS reference, return_date AS date, "
                "'sales_return' AS type, 0 AS debit, total_amount AS credit, status "
                "FROM sales_returns WHERE customer_id = :cid AND is_deleted = FALSE "
                "AND status = 'confirmed' "
                "ORDER BY return_date DESC"
            ),
            {"cid": str(customer_id)},
        ).mappings().all()
    except SQLAlchemyError:
        returns = []

    items = [dict(row) for row in list(invoices) + list(receipts) + list(returns)]
    items.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return {"items": items}


@router.get("/{customer_id}/balance", response_model=CustomerBalanceResponse)
async def customer_balance(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_read")),
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _customer_balance(db, customer.id)

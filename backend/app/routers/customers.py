"""Customer master router."""
import re
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.customer import Customer
from app.models.customization_option import CustomizationOption
from app.models.user import User
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerResponse,
    CustomersListResponse,
    CustomerBalanceResponse,
    CustomerCustomizationOptionsResponse,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


STATE_ABBREVIATIONS = {
    "andhra pradesh": "AP",
    "arunachal pradesh": "AR",
    "assam": "AS",
    "bihar": "BR",
    "chhattisgarh": "CG",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "manipur": "MN",
    "meghalaya": "ML",
    "mizoram": "MZ",
    "nagaland": "NL",
    "odisha": "OD",
    "punjab": "PB",
    "rajasthan": "RJ",
    "sikkim": "SK",
    "tamil nadu": "TN",
    "telangana": "TS",
    "tripura": "TR",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
    "delhi": "DL",
}

DEFAULT_CUSTOMER_COUNTRIES = [
    "India",
    "United States",
    "United Arab Emirates",
    "United Kingdom",
    "Singapore",
    "Australia",
]

DEFAULT_CUSTOMER_CURRENCIES = ["INR", "USD", "EUR", "GBP"]
DEFAULT_CUSTOMER_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Delhi",
]


def _state_code_from_payload(payload: CustomerCreateRequest | CustomerUpdateRequest) -> str:
    state = (payload.billing_state or "").strip().lower()
    if state and state in STATE_ABBREVIATIONS:
        return STATE_ABBREVIATIONS[state]

    raw_state_code = (payload.billing_state_code or "").strip().upper()
    alpha_state_code = "".join(ch for ch in raw_state_code if ch.isalpha())
    if len(alpha_state_code) >= 2:
        return alpha_state_code[:2]

    if state:
        cleaned = "".join(ch for ch in state if ch.isalpha())
        if len(cleaned) >= 2:
            return cleaned[:2].upper()
    return "NA"


def _is_international(payload: CustomerCreateRequest | CustomerUpdateRequest) -> bool:
    if payload.business_type == "international":
        return True
    country = (payload.billing_country or "").strip().lower()
    return bool(country and country not in {"india", "in"})


def _generate_customer_code(db: Session, payload: CustomerCreateRequest | CustomerUpdateRequest) -> str:
    prefix = "CUST-INT" if _is_international(payload) else f"CUST-{_state_code_from_payload(payload)}"
    existing_codes = (
        db.query(Customer.customer_code)
        .filter(Customer.customer_code.like(f"{prefix}-%"))
        .all()
    )

    max_seq = 0
    for (code,) in existing_codes:
        if not code:
            continue
        match = re.search(r"-(\d{5})$", code)
        if match:
            max_seq = max(max_seq, int(match.group(1)))

    return f"{prefix}-{str(max_seq + 1).zfill(5)}"


def _apply_gstin_policy(payload: CustomerCreateRequest | CustomerUpdateRequest) -> None:
    if payload.gstin_status == "non-registered":
        payload.gstin = None


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
        payload.shipping_country = payload.billing_country
        payload.shipping_pincode = payload.billing_pincode


def _normalize_customer_currency(payload: CustomerCreateRequest | CustomerUpdateRequest) -> None:
    currency = (payload.currency_code or "").strip().upper()
    payload.currency_code = currency or "INR"


def _normalize_country(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_state(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _upsert_customer_customization_option(
    db: Session,
    *,
    field_name: str,
    option_value: str,
    created_by: UUID | None,
) -> None:
    existing = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.module == "customer",
            CustomizationOption.field_name == field_name,
            func.lower(CustomizationOption.option_value) == option_value.lower(),
            CustomizationOption.is_deleted == False,
        )
        .first()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
        return

    db.add(
        CustomizationOption(
            module="customer",
            field_name=field_name,
            option_value=option_value,
            display_label=option_value,
            is_active=True,
            created_by=created_by,
        )
    )


def _persist_customer_customization_values(
    db: Session,
    payload: CustomerCreateRequest | CustomerUpdateRequest,
    created_by: UUID | None,
) -> None:
    currency = (payload.currency_code or "").strip().upper()
    if currency:
        _upsert_customer_customization_option(
            db,
            field_name="currency",
            option_value=currency,
            created_by=created_by,
        )

    billing_country = _normalize_country(payload.billing_country)
    if billing_country:
        _upsert_customer_customization_option(
            db,
            field_name="country",
            option_value=billing_country,
            created_by=created_by,
        )

    if not payload.same_as_billing:
        shipping_country = _normalize_country(payload.shipping_country)
        if shipping_country:
            _upsert_customer_customization_option(
                db,
                field_name="country",
                option_value=shipping_country,
                created_by=created_by,
            )

    billing_state = _normalize_state(payload.billing_state)
    if billing_state:
        _upsert_customer_customization_option(
            db,
            field_name="state",
            option_value=billing_state,
            created_by=created_by,
        )

    if not payload.same_as_billing:
        shipping_state = _normalize_state(payload.shipping_state)
        if shipping_state:
            _upsert_customer_customization_option(
                db,
                field_name="state",
                option_value=shipping_state,
                created_by=created_by,
            )


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


@router.get("/customization-options", response_model=CustomerCustomizationOptionsResponse)
async def get_customer_customization_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_read")),
):
    rows = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.module == "customer",
            CustomizationOption.field_name.in_(["country", "currency", "state"]),
            CustomizationOption.is_active == True,
            CustomizationOption.is_deleted == False,
        )
        .order_by(CustomizationOption.field_name.asc(), CustomizationOption.sort_order.asc(), CustomizationOption.option_value.asc())
        .all()
    )

    countries = sorted(
        {
            _normalize_country(row.option_value)
            for row in rows
            if row.field_name == "country" and _normalize_country(row.option_value)
        },
        key=lambda value: value.lower(),
    )
    currencies = sorted(
        {
            (row.option_value or "").strip().upper()
            for row in rows
            if row.field_name == "currency" and (row.option_value or "").strip()
        }
    )
    states = sorted(
        {
            _normalize_state(row.option_value)
            for row in rows
            if row.field_name == "state" and _normalize_state(row.option_value)
        },
        key=lambda value: value.lower(),
    )

    if not countries:
        countries = DEFAULT_CUSTOMER_COUNTRIES.copy()
    if not currencies:
        currencies = DEFAULT_CUSTOMER_CURRENCIES.copy()
    if not states:
        states = DEFAULT_CUSTOMER_STATES.copy()

    return CustomerCustomizationOptionsResponse(countries=countries, currencies=currencies, states=states)


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    payload: CustomerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("customers_write")),
):
    _apply_gstin_policy(payload)
    _normalize_customer_currency(payload)

    if payload.gstin:
        duplicate = db.query(Customer).filter(Customer.gstin == payload.gstin, Customer.is_deleted == False).first()
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "DUPLICATE_GSTIN", "message": "GSTIN already exists"},
            )

    _apply_gstin_state_code(payload)
    _normalize_shipping(payload)
    _persist_customer_customization_values(db, payload, current_user.id)

    customer = Customer(
        **payload.model_dump(exclude={"customer_code"}),
        customer_code=payload.customer_code or _generate_customer_code(db, payload),
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

    _apply_gstin_policy(payload)
    _normalize_customer_currency(payload)

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
    _persist_customer_customization_values(db, payload, current_user.id)

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

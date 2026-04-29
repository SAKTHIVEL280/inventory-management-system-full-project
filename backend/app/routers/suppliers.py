"""Supplier master router."""
import re
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import enforce_resource_ownership, require_permissions
from app.models.customization_option import CustomizationOption
from app.models.supplier import Supplier
from app.models.user import User
from app.services.data_masking import DataMasker, should_mask_sensitive_fields
from app.utils.input_validation import normalize_search_query
from app.utils.state_mappings import (
    canonical_state_code,
    state_abbreviation_from_code,
    validate_and_autofill_state_fields,
)
from app.schemas.supplier import (
    SupplierCreateRequest,
    SupplierCustomizationOptionsResponse,
    SupplierUpdateRequest,
    SupplierResponse,
    SuppliersListResponse,
    SupplierBalanceResponse,
)

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


def _scope_to_owner(query, model_cls, current_user: User):
    if current_user.role in {"admin", "accounts"}:
        return query
    owner_col = getattr(model_cls, "created_by", None)
    if owner_col is None:
        return query
    return query.filter(or_(owner_col == current_user.id, owner_col.is_(None)))


STATE_ABBREVIATIONS = {
    "andaman and nicobar islands": "AN",
    "andhra pradesh": "AP",
    "arunachal pradesh": "AR",
    "assam": "AS",
    "bihar": "BR",
    "chandigarh": "CH",
    "chhattisgarh": "CG",
    "dadra and nagar haveli and daman and diu": "DD",
    "delhi": "DL",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jammu and kashmir": "JK",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "ladakh": "LA",
    "lakshadweep": "LD",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "manipur": "MN",
    "meghalaya": "ML",
    "mizoram": "MZ",
    "nagaland": "NL",
    "odisha": "OD",
    "punjab": "PB",
    "puducherry": "PY",
    "rajasthan": "RJ",
    "sikkim": "SK",
    "tamil nadu": "TN",
    "telangana": "TS",
    "tripura": "TR",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
}

DEFAULT_SUPPLIER_COUNTRIES = [
    "India",
    "United States",
    "United Arab Emirates",
    "United Kingdom",
    "Singapore",
    "Australia",
]

DEFAULT_SUPPLIER_CURRENCIES = ["INR", "USD", "EUR", "GBP"]
DEFAULT_SUPPLIER_STATES = [
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Puducherry",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]


def _state_code_from_payload(payload: SupplierCreateRequest | SupplierUpdateRequest) -> str:
    canonical_code = canonical_state_code(payload.state_code)
    if canonical_code:
        return canonical_code

    state = (payload.state or "").strip().lower()
    if state and state in STATE_ABBREVIATIONS:
        code = canonical_state_code(STATE_ABBREVIATIONS[state])
        if code:
            return code

    if state:
        cleaned = "".join(ch for ch in state if ch.isalpha())
        if len(cleaned) >= 2:
            code = canonical_state_code(cleaned[:2].upper())
            if code:
                return code
    return "NA"


def _state_prefix_from_payload(payload: SupplierCreateRequest | SupplierUpdateRequest) -> str:
    code = _state_code_from_payload(payload)
    if code == "NA":
        return "NA"

    abbr = state_abbreviation_from_code(code)
    return abbr or "NA"


def _is_international(payload: SupplierCreateRequest | SupplierUpdateRequest) -> bool:
    if payload.business_type == "international":
        return True
    country = (payload.billing_country or "").strip().lower()
    return bool(country and country not in {"india", "in"})


def _generate_supplier_code(db: Session, payload: SupplierCreateRequest | SupplierUpdateRequest) -> str:
    prefix = "SUPP-INT" if _is_international(payload) else f"SUPP-{_state_prefix_from_payload(payload)}"
    existing_codes = (
        db.query(Supplier.supplier_code)
        .filter(Supplier.supplier_code.like(f"{prefix}-%"))
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


def _apply_gstin_policy(payload: SupplierCreateRequest | SupplierUpdateRequest) -> None:
    if payload.gstin_status == "non-registered":
        payload.gstin = None


def _normalize_supplier_currency(payload: SupplierCreateRequest | SupplierUpdateRequest) -> None:
    currency = (payload.currency_code or "").strip().upper()
    payload.currency_code = currency or "INR"


def _normalize_country(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_state(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _validate_and_autofill_supplier_state(payload: SupplierCreateRequest | SupplierUpdateRequest) -> None:
    try:
        payload.state, payload.state_code = validate_and_autofill_state_fields(
            payload.state,
            payload.state_code,
            field_label="State",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _upsert_supplier_customization_option(
    db: Session,
    *,
    field_name: str,
    option_value: str,
    created_by: UUID | None,
) -> None:
    existing = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.module == "supplier",
            CustomizationOption.field_name == field_name,
            func.lower(CustomizationOption.option_value) == option_value.lower(),
        )
        .first()
    )
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.deleted_at = None
        if not existing.is_active:
            existing.is_active = True
        if not existing.display_label:
            existing.display_label = existing.option_value
        return

    db.add(
        CustomizationOption(
            module="supplier",
            field_name=field_name,
            option_value=option_value,
            display_label=option_value,
            is_active=True,
            created_by=created_by,
        )
    )


def _persist_supplier_customization_values(
    db: Session,
    payload: SupplierCreateRequest | SupplierUpdateRequest,
    created_by: UUID | None,
) -> None:
    currency = (payload.currency_code or "").strip().upper()
    if currency:
        _upsert_supplier_customization_option(
            db,
            field_name="currency",
            option_value=currency,
            created_by=created_by,
        )

    country = _normalize_country(payload.billing_country)
    if country:
        _upsert_supplier_customization_option(
            db,
            field_name="country",
            option_value=country,
            created_by=created_by,
        )

    state = _normalize_state(payload.state)
    if state:
        _upsert_supplier_customization_option(
            db,
            field_name="state",
            option_value=state,
            created_by=created_by,
        )


def _supplier_balance(db: Session, supplier_id: UUID) -> SupplierBalanceResponse:
    """Calculate supplier balance from confirmed GRNs and cleared payments."""
    try:
        purchased = db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM goods_receipt_notes "
                "WHERE supplier_id = :supplier_id AND is_deleted = FALSE "
                "AND status = 'confirmed'"
            ),
            {"supplier_id": str(supplier_id)},
        ).scalar_one()
        paid = db.execute(
            text(
                "SELECT COALESCE(SUM(amount), 0) FROM payments "
                "WHERE supplier_id = :supplier_id AND payment_type = 'payment' "
                "AND status = 'cleared' AND is_deleted = FALSE"
            ),
            {"supplier_id": str(supplier_id)},
        ).scalar_one()
    except SQLAlchemyError:
        purchased = 0
        paid = 0

    return SupplierBalanceResponse(
        total_purchased=int(purchased or 0),
        total_paid=int(paid or 0),
        balance_due=int((purchased or 0) - (paid or 0)),
    )


def _to_supplier_response(supplier: Supplier, current_user: User) -> SupplierResponse:
    response = SupplierResponse.model_validate(supplier)
    if not should_mask_sensitive_fields(current_user.role):
        return response

    payload = response.model_dump()
    payload["email"] = DataMasker.mask_email(payload.get("email"))
    payload["phone"] = DataMasker.mask_phone(payload.get("phone"))
    payload["alternate_phone"] = DataMasker.mask_phone(payload.get("alternate_phone"))
    payload["pan"] = DataMasker.mask_pan(payload.get("pan"))
    payload["gstin"] = DataMasker.mask_gstin(payload.get("gstin"))
    payload["bank_account_no"] = DataMasker.mask_bank_account(payload.get("bank_account_no"))
    return SupplierResponse.model_validate(payload)


@router.get("", response_model=SuppliersListResponse)
async def list_suppliers(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_read")),
):
    search = normalize_search_query(search)
    query = db.query(Supplier).filter(Supplier.is_deleted == False)
    query = _scope_to_owner(query, Supplier, current_user)

    if search:
        like_text = f"%{search}%"
        query = query.filter(
            or_(
                Supplier.supplier_code.ilike(like_text),
                Supplier.company_name.ilike(like_text),
                Supplier.phone.ilike(like_text),
            )
        )

    if is_active is not None:
        query = query.filter(Supplier.is_active == is_active)

    total = query.count()
    items = (
        query.order_by(Supplier.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return SuppliersListResponse(
        items=[_to_supplier_response(item, current_user) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/customization-options", response_model=SupplierCustomizationOptionsResponse)
async def get_supplier_customization_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_read")),
):
    rows = (
        db.query(CustomizationOption)
        .filter(
            CustomizationOption.module == "supplier",
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
        countries = DEFAULT_SUPPLIER_COUNTRIES.copy()
    if not currencies:
        currencies = DEFAULT_SUPPLIER_CURRENCIES.copy()
    if not states:
        states = DEFAULT_SUPPLIER_STATES.copy()

    return SupplierCustomizationOptionsResponse(countries=countries, currencies=currencies, states=states)


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_write")),
):
    _apply_gstin_policy(payload)
    _normalize_supplier_currency(payload)
    _validate_and_autofill_supplier_state(payload)

    if payload.gstin:
        duplicate = db.query(Supplier).filter(Supplier.gstin == payload.gstin, Supplier.is_deleted == False).first()
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "DUPLICATE_GSTIN", "message": "GSTIN already exists"},
            )

    _persist_supplier_customization_values(db, payload, current_user.id)

    supplier = Supplier(
        **payload.model_dump(exclude={"supplier_code", "state_code"}),
        supplier_code=payload.supplier_code or _generate_supplier_code(db, payload),
        state_code=_state_code_from_payload(payload),
        created_by=current_user.id,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_read")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    enforce_resource_ownership(supplier.created_by, current_user)
    return _to_supplier_response(supplier, current_user)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    enforce_resource_ownership(supplier.created_by, current_user)

    _apply_gstin_policy(payload)
    _normalize_supplier_currency(payload)
    _validate_and_autofill_supplier_state(payload)

    if payload.gstin:
        duplicate = (
            db.query(Supplier)
            .filter(Supplier.gstin == payload.gstin, Supplier.id != supplier_id, Supplier.is_deleted == False)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "DUPLICATE_GSTIN", "message": "GSTIN already exists"},
            )

    _persist_supplier_customization_values(db, payload, current_user.id)

    for field, value in payload.model_dump(exclude={"supplier_code"}).items():
        setattr(supplier, field, value)
    supplier.state_code = _state_code_from_payload(payload)

    db.commit()
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    enforce_resource_ownership(supplier.created_by, current_user)

    supplier.is_deleted = True
    supplier.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "Supplier deleted"}


@router.get("/{supplier_id}/ledger")
async def supplier_ledger(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_read")),
):
    """BUG-41 fix: Return actual transaction history for the supplier."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    enforce_resource_ownership(supplier.created_by, current_user)

    # Fetch confirmed GRNs
    try:
        grns = db.execute(
            text(
                "SELECT id, grn_number AS reference, receipt_date AS date, "
                "'grn' AS type, total_amount AS debit, 0 AS credit, status "
                "FROM goods_receipt_notes WHERE supplier_id = :sid AND is_deleted = FALSE "
                "AND status = 'confirmed' "
                "ORDER BY receipt_date DESC"
            ),
            {"sid": str(supplier_id)},
        ).mappings().all()
    except SQLAlchemyError:
        grns = []

    # Fetch cleared payments
    try:
        payments = db.execute(
            text(
                "SELECT id, payment_number AS reference, payment_date AS date, "
                "'payment' AS type, 0 AS debit, amount AS credit, status "
                "FROM payments WHERE supplier_id = :sid AND payment_type = 'payment' "
                "AND status = 'cleared' AND is_deleted = FALSE "
                "ORDER BY payment_date DESC"
            ),
            {"sid": str(supplier_id)},
        ).mappings().all()
    except SQLAlchemyError:
        payments = []

    # Fetch confirmed purchase returns
    try:
        returns = db.execute(
            text(
                "SELECT id, return_number AS reference, return_date AS date, "
                "'purchase_return' AS type, 0 AS debit, total_amount AS credit, status "
                "FROM purchase_returns WHERE supplier_id = :sid AND is_deleted = FALSE "
                "AND status = 'confirmed' "
                "ORDER BY return_date DESC"
            ),
            {"sid": str(supplier_id)},
        ).mappings().all()
    except SQLAlchemyError:
        returns = []

    items = [dict(row) for row in list(grns) + list(payments) + list(returns)]
    items.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return {"items": items}


@router.get("/{supplier_id}/balance", response_model=SupplierBalanceResponse)
async def supplier_balance(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_read")),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    enforce_resource_ownership(supplier.created_by, current_user)
    return _supplier_balance(db, supplier.id)

"""Supplier master router."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.supplier import (
    SupplierCreateRequest,
    SupplierUpdateRequest,
    SupplierResponse,
    SuppliersListResponse,
    SupplierBalanceResponse,
)

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


def _generate_supplier_code(db: Session) -> str:
    count = db.query(Supplier).count()
    return f"SUPP-{str(count + 1).zfill(5)}"


def _apply_gstin_state_code(payload: SupplierCreateRequest | SupplierUpdateRequest) -> None:
    if payload.gstin and len(payload.gstin) >= 2 and not payload.state_code:
        payload.state_code = payload.gstin[:2]


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


@router.get("", response_model=SuppliersListResponse)
async def list_suppliers(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_read")),
):
    query = db.query(Supplier).filter(Supplier.is_deleted == False)

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
        items=[SupplierResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("suppliers_write")),
):
    if payload.gstin:
        duplicate = db.query(Supplier).filter(Supplier.gstin == payload.gstin, Supplier.is_deleted == False).first()
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "DUPLICATE_GSTIN", "message": "GSTIN already exists"},
            )

    _apply_gstin_state_code(payload)

    supplier = Supplier(
        **payload.model_dump(exclude={"supplier_code"}),
        supplier_code=payload.supplier_code or _generate_supplier_code(db),
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
    return SupplierResponse.model_validate(supplier)


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

    _apply_gstin_state_code(payload)

    for field, value in payload.model_dump(exclude={"supplier_code"}).items():
        setattr(supplier, field, value)

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
    return _supplier_balance(db, supplier.id)

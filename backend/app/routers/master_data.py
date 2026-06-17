"""Sales master-data router (Stockist, Sales Manager).

Enhancement 3 — masters managed under Customization. Reads are available to any
authenticated user (the Sales Invoice form needs the dropdowns); writes are
admin-only (FR-20). Entries are company-scoped and soft-deleted so invoices that
reference an entry keep working after it is deactivated/removed.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.master_data import SalesManager, Stockist
from app.models.user import User
from app.schemas.master_data import (
    SalesManagerCreateRequest,
    SalesManagerResponse,
    SalesManagerUpdateRequest,
    SalesManagersListResponse,
    StockistCreateRequest,
    StockistResponse,
    StockistUpdateRequest,
    StockistsListResponse,
)

router = APIRouter(prefix="/api/v1", tags=["master-data"])


def _normalize(value: str | None) -> str:
    return (value or "").strip()


def _scope_to_company(query, model, current_user: User):
    """Show the company's own entries plus any legacy/global (NULL) entries."""
    if current_user.company_id is not None:
        return query.filter(
            or_(model.company_id == current_user.company_id, model.company_id.is_(None))
        )
    return query


# ────────────────────────────── Stockists ────────────────────────────────────
@router.get("/stockists", response_model=StockistsListResponse)
async def list_stockists(
    search: str | None = Query(default=None, max_length=120),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Stockist).filter(Stockist.is_deleted == False)
    query = _scope_to_company(query, Stockist, current_user)
    if not include_inactive:
        query = query.filter(Stockist.is_active == True)
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(or_(Stockist.name.ilike(token), Stockist.city.ilike(token)))

    total = query.count()
    rows = (
        query.order_by(Stockist.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return StockistsListResponse(
        items=[StockistResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("/stockists", response_model=StockistResponse, status_code=201)
async def create_stockist(
    payload: StockistCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    name = _normalize(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Stockist Name is required")

    existing = (
        db.query(Stockist)
        .filter(
            func.lower(Stockist.name) == name.lower(),
            Stockist.is_deleted == False,
        )
    )
    existing = _scope_to_company(existing, Stockist, current_user).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Stockist '{name}' already exists")

    stockist = Stockist(
        name=name,
        city=_normalize(payload.city) or None,
        is_active=payload.is_active,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(stockist)
    db.commit()
    db.refresh(stockist)
    return StockistResponse.model_validate(stockist)


@router.put("/stockists/{stockist_id}", response_model=StockistResponse)
async def update_stockist(
    stockist_id: UUID,
    payload: StockistUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    stockist = (
        db.query(Stockist)
        .filter(Stockist.id == stockist_id, Stockist.is_deleted == False)
        .first()
    )
    if not stockist:
        raise HTTPException(status_code=404, detail="Stockist not found")

    if payload.name is not None:
        new_name = _normalize(payload.name)
        if not new_name:
            raise HTTPException(status_code=400, detail="Stockist Name is required")
        duplicate = (
            db.query(Stockist)
            .filter(
                func.lower(Stockist.name) == new_name.lower(),
                Stockist.id != stockist.id,
                Stockist.is_deleted == False,
            )
        )
        duplicate = _scope_to_company(duplicate, Stockist, current_user).first()
        if duplicate:
            raise HTTPException(status_code=400, detail=f"Stockist '{new_name}' already exists")
        stockist.name = new_name
    if payload.city is not None:
        stockist.city = _normalize(payload.city) or None
    if payload.is_active is not None:
        stockist.is_active = payload.is_active

    db.commit()
    db.refresh(stockist)
    return StockistResponse.model_validate(stockist)


@router.delete("/stockists/{stockist_id}", status_code=204)
async def delete_stockist(
    stockist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    stockist = (
        db.query(Stockist)
        .filter(Stockist.id == stockist_id, Stockist.is_deleted == False)
        .first()
    )
    if not stockist:
        raise HTTPException(status_code=404, detail="Stockist not found")
    stockist.is_deleted = True
    stockist.is_active = False
    stockist.deleted_at = datetime.utcnow()
    db.commit()
    return None


# ───────────────────────────── Sales Managers ────────────────────────────────
@router.get("/sales-managers", response_model=SalesManagersListResponse)
async def list_sales_managers(
    search: str | None = Query(default=None, max_length=120),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(SalesManager).filter(SalesManager.is_deleted == False)
    query = _scope_to_company(query, SalesManager, current_user)
    if not include_inactive:
        query = query.filter(SalesManager.is_active == True)
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SalesManager.name.ilike(token),
                SalesManager.region.ilike(token),
                SalesManager.employee_id.ilike(token),
            )
        )

    total = query.count()
    rows = (
        query.order_by(SalesManager.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SalesManagersListResponse(
        items=[SalesManagerResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("/sales-managers", response_model=SalesManagerResponse, status_code=201)
async def create_sales_manager(
    payload: SalesManagerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    name = _normalize(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Sales Manager Name is required")

    existing = (
        db.query(SalesManager)
        .filter(
            func.lower(SalesManager.name) == name.lower(),
            SalesManager.is_deleted == False,
        )
    )
    existing = _scope_to_company(existing, SalesManager, current_user).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Sales Manager '{name}' already exists")

    manager = SalesManager(
        name=name,
        employee_id=_normalize(payload.employee_id) or None,
        region=_normalize(payload.region) or None,
        is_active=payload.is_active,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    return SalesManagerResponse.model_validate(manager)


@router.put("/sales-managers/{manager_id}", response_model=SalesManagerResponse)
async def update_sales_manager(
    manager_id: UUID,
    payload: SalesManagerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    manager = (
        db.query(SalesManager)
        .filter(SalesManager.id == manager_id, SalesManager.is_deleted == False)
        .first()
    )
    if not manager:
        raise HTTPException(status_code=404, detail="Sales Manager not found")

    if payload.name is not None:
        new_name = _normalize(payload.name)
        if not new_name:
            raise HTTPException(status_code=400, detail="Sales Manager Name is required")
        duplicate = (
            db.query(SalesManager)
            .filter(
                func.lower(SalesManager.name) == new_name.lower(),
                SalesManager.id != manager.id,
                SalesManager.is_deleted == False,
            )
        )
        duplicate = _scope_to_company(duplicate, SalesManager, current_user).first()
        if duplicate:
            raise HTTPException(status_code=400, detail=f"Sales Manager '{new_name}' already exists")
        manager.name = new_name
    if payload.employee_id is not None:
        manager.employee_id = _normalize(payload.employee_id) or None
    if payload.region is not None:
        manager.region = _normalize(payload.region) or None
    if payload.is_active is not None:
        manager.is_active = payload.is_active

    db.commit()
    db.refresh(manager)
    return SalesManagerResponse.model_validate(manager)


@router.delete("/sales-managers/{manager_id}", status_code=204)
async def delete_sales_manager(
    manager_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    manager = (
        db.query(SalesManager)
        .filter(SalesManager.id == manager_id, SalesManager.is_deleted == False)
        .first()
    )
    if not manager:
        raise HTTPException(status_code=404, detail="Sales Manager not found")
    manager.is_deleted = True
    manager.is_active = False
    manager.deleted_at = datetime.utcnow()
    db.commit()
    return None

"""Customization options admin router."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.customization_option import CustomizationOption
from app.schemas.customization_option import (
    CustomizationOptionCreateRequest,
    CustomizationOptionResponse,
    CustomizationOptionUpdateRequest,
    CustomizationOptionsListResponse,
)

router = APIRouter(prefix="/api/v1/customization-options", tags=["customization-options"])


def _normalize_token(value: str | None) -> str:
    return (value or "").strip()


def _normalize_scope(module: str, field_name: str) -> tuple[str, str]:
    return module.strip().lower(), field_name.strip().lower()


@router.get("", response_model=CustomizationOptionsListResponse)
async def list_customization_options(
    module: str | None = Query(default=None, max_length=50),
    field_name: str | None = Query(default=None, max_length=50),
    search: str | None = Query(default=None, max_length=120),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    query = db.query(CustomizationOption).filter(CustomizationOption.is_deleted == False)

    if module:
        query = query.filter(func.lower(CustomizationOption.module) == module.strip().lower())
    if field_name:
        query = query.filter(func.lower(CustomizationOption.field_name) == field_name.strip().lower())
    if not include_inactive:
        query = query.filter(CustomizationOption.is_active == True)
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(
            or_(
                CustomizationOption.option_value.ilike(token),
                CustomizationOption.display_label.ilike(token),
            )
        )

    total = query.count()
    rows = (
        query.order_by(
            CustomizationOption.module.asc(),
            CustomizationOption.field_name.asc(),
            CustomizationOption.sort_order.asc(),
            CustomizationOption.option_value.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CustomizationOptionsListResponse(
        items=[CustomizationOptionResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("", response_model=CustomizationOptionResponse, status_code=201)
async def create_customization_option(
    payload: CustomizationOptionCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    module, field_name = _normalize_scope(payload.module, payload.field_name)
    option_value = _normalize_token(payload.option_value)
    display_label = _normalize_token(payload.display_label) or option_value

    existing = (
        db.query(CustomizationOption)
        .filter(
            func.lower(CustomizationOption.module) == module,
            func.lower(CustomizationOption.field_name) == field_name,
            func.lower(CustomizationOption.option_value) == option_value.lower(),
        )
        .first()
    )
    if existing:
        if not existing.is_deleted:
            raise HTTPException(status_code=400, detail="Customization option already exists")
        existing.is_deleted = False
        existing.deleted_at = None
        existing.is_active = payload.is_active
        existing.display_label = display_label
        existing.sort_order = payload.sort_order
        db.commit()
        db.refresh(existing)
        return CustomizationOptionResponse.model_validate(existing)

    option = CustomizationOption(
        module=module,
        field_name=field_name,
        option_value=option_value,
        display_label=display_label,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        created_by=getattr(current_user, "id", None),
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    return CustomizationOptionResponse.model_validate(option)


@router.put("/{option_id}", response_model=CustomizationOptionResponse)
async def update_customization_option(
    option_id: UUID,
    payload: CustomizationOptionUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    option = (
        db.query(CustomizationOption)
        .filter(CustomizationOption.id == option_id, CustomizationOption.is_deleted == False)
        .first()
    )
    if not option:
        raise HTTPException(status_code=404, detail="Customization option not found")

    module = option.module
    field_name = option.field_name
    option_value = option.option_value

    if payload.module is not None:
        module = _normalize_token(payload.module).lower()
    if payload.field_name is not None:
        field_name = _normalize_token(payload.field_name).lower()
    if payload.option_value is not None:
        option_value = _normalize_token(payload.option_value)

    duplicate = (
        db.query(CustomizationOption)
        .filter(
            func.lower(CustomizationOption.module) == module,
            func.lower(CustomizationOption.field_name) == field_name,
            func.lower(CustomizationOption.option_value) == option_value.lower(),
            CustomizationOption.id != option.id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Customization option already exists")

    option.module = module
    option.field_name = field_name
    option.option_value = option_value

    if payload.display_label is not None:
        option.display_label = _normalize_token(payload.display_label) or option_value
    if payload.sort_order is not None:
        option.sort_order = payload.sort_order
    if payload.is_active is not None:
        option.is_active = payload.is_active

    db.commit()
    db.refresh(option)
    return CustomizationOptionResponse.model_validate(option)


@router.delete("/{option_id}", status_code=204)
async def delete_customization_option(
    option_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    option = (
        db.query(CustomizationOption)
        .filter(CustomizationOption.id == option_id, CustomizationOption.is_deleted == False)
        .first()
    )
    if not option:
        raise HTTPException(status_code=404, detail="Customization option not found")

    option.is_deleted = True
    option.is_active = False
    option.deleted_at = datetime.utcnow()
    db.commit()
    return None

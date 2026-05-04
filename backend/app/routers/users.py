"""User management router."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_permissions
from app.models.user import User
from app.schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
    UserPermissionsUpdateRequest,
    UserManagementResponse,
    UsersListResponse,
)
from app.services.auth_service import hash_password, calculate_effective_access

router = APIRouter(prefix="/api/v1/users", tags=["users"])


ADMIN_ONLY_PERMISSIONS = {
    "company_read",
    "company_write",
    "users_read",
    "users_write",
    "action_logs_read",
}


def _scope_to_company(query, current_user: User):
    if current_user.company_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a company")
    return query.filter(User.company_id == current_user.company_id)


def _to_user_response(user: User) -> UserManagementResponse:
    return UserManagementResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        permission_overrides=user.permission_overrides,
        effective_access=calculate_effective_access(user.role, user.permission_overrides),
        force_password_change=user.force_password_change,
        is_active=user.is_active,
    )


@router.get("", response_model=UsersListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_read")),
):
    query = db.query(User).filter(User.is_deleted == False)
    query = _scope_to_company(query, current_user)
    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_to_user_response(user) for user in users]
    return UsersListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("", response_model=UserManagementResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_write")),
):
    existing = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.email == payload.email, User.is_deleted == False)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    if payload.role != "admin" and payload.permission_overrides:
        allow = payload.permission_overrides.get("allow", [])
        if any(permission in ADMIN_ONLY_PERMISSIONS for permission in allow):
            raise HTTPException(status_code=400, detail="Admin-only modules cannot be granted")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        permission_overrides=payload.permission_overrides,
        is_active=payload.is_active,
        force_password_change=True,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.get("/{user_id}", response_model=UserManagementResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_read")),
):
    user = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_user_response(user)


@router.put("/{user_id}", response_model=UserManagementResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_write")),
):
    user = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    email_owner = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.email == payload.email, User.id != user_id, User.is_deleted == False)
        .first()
    )
    if email_owner:
        raise HTTPException(status_code=400, detail="Email already exists")

    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Admin cannot deactivate their own account")

    if payload.role != "admin" and payload.permission_overrides:
        allow = payload.permission_overrides.get("allow", [])
        if any(permission in ADMIN_ONLY_PERMISSIONS for permission in allow):
            raise HTTPException(status_code=400, detail="Admin-only modules cannot be granted")

    user.full_name = payload.full_name
    user.email = payload.email
    user.role = payload.role
    user.permission_overrides = payload.permission_overrides
    user.is_active = payload.is_active

    if payload.password:
        user.hashed_password = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.patch("/{user_id}/permissions", response_model=UserManagementResponse)
async def update_user_permissions(
    user_id: UUID,
    payload: UserPermissionsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_write")),
):
    user = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != "admin" and any(permission in ADMIN_ONLY_PERMISSIONS for permission in payload.allow):
        raise HTTPException(status_code=400, detail="Admin-only modules cannot be granted")

    user.permission_overrides = {
        "allow": payload.allow,
        "deny": payload.deny,
    }
    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.delete("/{user_id}/permissions", response_model=UserManagementResponse)
async def clear_user_permissions(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_write")),
):
    user = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.permission_overrides = None
    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("users_write")),
):
    user = (
        _scope_to_company(db.query(User), current_user)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Admin cannot delete their own account")

    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "User deleted"}

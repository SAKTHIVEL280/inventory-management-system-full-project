"""User management router."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
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


def _is_last_active_admin(db, current_user: User, user: User) -> bool:
    """True if `user` is the tenant's only active Administrator.

    Used to prevent deleting, deactivating, or role-changing the last Admin so a
    tenant always retains at least one Administrator.
    """
    from app.services.auth_service import normalize_role

    if normalize_role(user.role) != "admin" or not user.is_active:
        return False
    count = 0
    for u in _scope_to_company(db.query(User), current_user).filter(
        User.is_deleted == False, User.is_active == True
    ).all():
        if normalize_role(u.role) == "admin":
            count += 1
    return count <= 1


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
    # Email must be globally unique across ALL tenants (excluding deleted users so a
    # deleted account's email can be reused).
    existing = (
        db.query(User)
        .filter(func.lower(User.email) == payload.email.strip().lower(), User.is_deleted == False)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="This email is already registered. Please use a different email.",
        )

    # Multi-tenant (M2): enforce the subscription plan's maximum user count.
    if current_user.company_id is not None:
        from app.models.company import Company
        from app.services.plan_service import (
            plan_user_limit, normalize_plan,
            role_allowed_for_plan, role_not_available_message,
        )

        company = (
            db.query(Company).filter(Company.id == current_user.company_id).first()
        )
        plan = getattr(company, "subscription_plan", None) if company else None
        limit = plan_user_limit(plan)
        # Count only ACTIVE users against the plan limit.
        active_users = (
            _scope_to_company(db.query(User), current_user)
            .filter(User.is_deleted == False, User.is_active == True)
            .count()
        )
        if active_users >= limit:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Your {normalize_plan(plan)} plan allows a maximum of {limit} "
                    f"user account(s). Please upgrade your subscription or deactivate "
                    f"an existing user to add a new one."
                ),
            )
        # Plan role availability (M3): the assigned role must be in the plan.
        if not role_allowed_for_plan(plan, payload.role):
            raise HTTPException(
                status_code=400,
                detail=role_not_available_message(plan, payload.role),
            )

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

    # Email is globally unique across tenants (excluding deleted users and self).
    email_owner = (
        db.query(User)
        .filter(
            func.lower(User.email) == payload.email.strip().lower(),
            User.id != user_id,
            User.is_deleted == False,
        )
        .first()
    )
    if email_owner:
        raise HTTPException(
            status_code=400,
            detail="This email is already registered. Please use a different email.",
        )

    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Admin cannot deactivate their own account")

    # Enforce the plan user limit when ACTIVATING/restoring a user (count active only).
    if payload.is_active and not user.is_active and current_user.company_id is not None:
        from app.models.company import Company
        from app.services.plan_service import plan_user_limit, normalize_plan

        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        plan = getattr(company, "subscription_plan", None) if company else None
        limit = plan_user_limit(plan)
        active_count = (
            _scope_to_company(db.query(User), current_user)
            .filter(User.is_deleted == False, User.is_active == True)
            .count()
        )
        if active_count >= limit:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Your {normalize_plan(plan)} plan allows a maximum of {limit} active "
                    f"user account(s). Deactivate another user or upgrade to activate this one."
                ),
            )

    # A tenant must always keep at least one Administrator: block demoting or
    # deactivating the last remaining Admin.
    from app.services.auth_service import normalize_role
    is_admin_now = normalize_role(user.role) == "admin"
    demoting = is_admin_now and normalize_role(payload.role) != "admin"
    deactivating = is_admin_now and payload.is_active is False
    if (demoting or deactivating) and _is_last_active_admin(db, current_user, user):
        raise HTTPException(
            status_code=400,
            detail="This is the tenant's only Administrator. Assign another Administrator first.",
        )

    # Plan role availability (M3): a changed role must be allowed by the plan.
    if getattr(payload, "role", None) and payload.role != user.role and current_user.company_id is not None:
        from app.models.company import Company
        from app.services.plan_service import role_allowed_for_plan, role_not_available_message

        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        plan = getattr(company, "subscription_plan", None) if company else None
        if not role_allowed_for_plan(plan, payload.role):
            raise HTTPException(
                status_code=400,
                detail=role_not_available_message(plan, payload.role),
            )

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

    if _is_last_active_admin(db, current_user, user):
        raise HTTPException(
            status_code=400,
            detail="This is the tenant's only Administrator. Assign another Administrator first.",
        )

    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "User deleted"}

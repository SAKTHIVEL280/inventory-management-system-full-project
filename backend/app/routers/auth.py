"""Authentication router."""
import secrets
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    create_access_token,
    create_refresh_token,
    get_current_user,
)
from app.models.user import User
from app.schemas.auth import (
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
)
from app.services.auth_service import (
    authenticate_user,
    get_user_response,
    verify_password,
    hash_password,
)
from app.services.audit_service import log_audit_event
from app.config import settings
from app.rate_limit import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_csrf_cookie(response: Response) -> None:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.refresh_token_expire_minutes * 60,
        secure=True,
        httponly=False,
        samesite="strict",
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Login endpoint - authenticates user and returns tokens.
    
    Returns:
        - access_token: JWT token for authenticated requests (8 hours)
        - refresh_token: JWT token for refreshing access token (8 hours)
        - user: User object with effective_access calculated
    
    Raises:
        - 401 if invalid credentials
        - 423 if account is locked (5 failed attempts → 30 min block)
    """
    try:
        user = authenticate_user(db, credentials.email, credentials.password)
    except ValueError as e:
        log_audit_event(
            db,
            action="LOGIN",
            resource_type="auth",
            status="failure",
            details={"email": credentials.email, "reason": str(e)},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        raise HTTPException(
            status_code=423,
            detail=str(e),
        )
    
    if not user:
        log_audit_event(
            db,
            action="LOGIN",
            resource_type="auth",
            status="failure",
            details={"email": credentials.email, "reason": "invalid_credentials"},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Keep bearer compatibility while migrating clients to cookie-based auth.
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.refresh_token_expire_minutes * 60,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    if settings.csrf_enabled:
        _set_csrf_cookie(response)

    log_audit_event(
        db,
        action="LOGIN",
        resource_type="auth",
        status="success",
        user_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=get_user_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("100/minute")
async def refresh(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Refresh access token using refresh token.
    
    Returns:
        - new access_token
        - same refresh_token
        - user: Updated user object
    """
    from jose import jwt, JWTError

    try:
        refresh_token = payload.refresh_token if payload else request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token",
            )

        jwt_payload = jwt.decode(
            refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = jwt_payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except JWTError:
        log_audit_event(
            db,
            action="TOKEN_REFRESH",
            resource_type="auth",
            status="failure",
            details={"reason": "invalid_refresh_token"},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True,
        User.is_deleted == False,
    ).first()

    if not user:
        log_audit_event(
            db,
            action="TOKEN_REFRESH",
            resource_type="auth",
            status="failure",
            details={"reason": "inactive_or_missing_user"},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    if settings.csrf_enabled:
        _set_csrf_cookie(response)

    log_audit_event(
        db,
        action="TOKEN_REFRESH",
        resource_type="auth",
        status="success",
        user_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=get_user_response(user),
    )


@router.get("/me")
@limiter.limit("100/minute")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user.
    
    BUG-11 fix: Returns just the user object with effective_access,
    not wrapped in TokenResponse with empty tokens.
    """
    return get_user_response(current_user)


@router.post("/logout")
@limiter.limit("100/minute")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Logout endpoint.
    
    Backend doesn't maintain token blacklist for now (stateless JWT).
    Browser session cookies are cleared on logout.
    """
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")

    log_audit_event(
        db,
        action="LOGOUT",
        resource_type="auth",
        status="success",
        user_id=current_user.id,
        details={"email": current_user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"message": "Logged out successfully"}


@router.post("/change-password")
@limiter.limit("100/minute")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user password - requires current password for verification.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        log_audit_event(
            db,
            action="CHANGE_PASSWORD",
            resource_type="auth",
            status="failure",
            user_id=current_user.id,
            details={"reason": "invalid_current_password"},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.force_password_change = False
    db.add(current_user)
    db.commit()

    log_audit_event(
        db,
        action="CHANGE_PASSWORD",
        resource_type="auth",
        status="success",
        user_id=current_user.id,
        details={"email": current_user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {"message": "Password changed successfully"}

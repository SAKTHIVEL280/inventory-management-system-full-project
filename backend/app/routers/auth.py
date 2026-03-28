"""Authentication router."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
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
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Login endpoint - authenticates user and returns tokens.
    
    Returns:
        - access_token: JWT token for authenticated requests (8 hours)
        - refresh_token: JWT token for refreshing access token (7 days)
        - user: User object with effective_access calculated
    """
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=get_user_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshTokenRequest,
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
        payload = jwt.decode(
            request.refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except JWTError:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,
        user=get_user_response(user),
    )


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user.
    
    BUG-11 fix: Returns just the user object with effective_access,
    not wrapped in TokenResponse with empty tokens.
    """
    return get_user_response(current_user)


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Logout endpoint - frontend should clear localStorage tokens.
    
    Backend doesn't maintain token blacklist for now (stateless JWT).
    Frontend is responsible for clearing tokens.
    """
    return {"message": "Logged out successfully"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user password - requires current password for verification.
    """
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(request.new_password)
    current_user.force_password_change = False
    db.add(current_user)
    db.commit()

    return {"message": "Password changed successfully"}

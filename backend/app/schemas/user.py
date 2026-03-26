"""User management schemas."""
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator


class UserCreateRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    permission_overrides: Optional[Dict[str, Any]] = None
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class UserUpdateRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: Optional[str] = None
    role: str
    permission_overrides: Optional[Dict[str, Any]] = None
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: Optional[str]) -> Optional[str]:
        if value and len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class UserPermissionsUpdateRequest(BaseModel):
    allow: List[str] = []
    deny: List[str] = []


class UserManagementResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: str
    permission_overrides: Optional[Dict[str, Any]] = None
    effective_access: List[str]
    force_password_change: bool
    is_active: bool

    class Config:
        from_attributes = True


class UsersListResponse(BaseModel):
    items: List[UserManagementResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

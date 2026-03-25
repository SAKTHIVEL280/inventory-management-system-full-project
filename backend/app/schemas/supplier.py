"""Supplier schemas."""
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, field_validator

GSTIN_REGEX = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"


class SupplierBase(BaseModel):
    supplier_code: Optional[str] = None
    company_name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: str
    alternate_phone: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    pincode: Optional[str] = None

    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None

    payment_terms_days: int = 30
    opening_balance: int = 0
    opening_balance_type: str = "cr"
    is_active: bool = True

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        import re

        upper_value = value.upper()
        if not re.match(GSTIN_REGEX, upper_value):
            raise ValueError("Invalid GSTIN format")
        return upper_value

    @field_validator("opening_balance_type")
    @classmethod
    def validate_opening_balance_type(cls, value: str) -> str:
        if value not in {"dr", "cr"}:
            raise ValueError("opening_balance_type must be dr or cr")
        return value


class SupplierCreateRequest(SupplierBase):
    pass


class SupplierUpdateRequest(SupplierBase):
    pass


class SupplierResponse(SupplierBase):
    id: UUID

    class Config:
        from_attributes = True


class SupplierBalanceResponse(BaseModel):
    total_purchased: int
    total_paid: int
    balance_due: int


class SuppliersListResponse(BaseModel):
    items: List[SupplierResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

"""Supplier schemas."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

GSTIN_REGEX = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"


class SupplierBase(BaseModel):
    supplier_code: Optional[str] = None
    company_name: str
    company_director_name: Optional[str] = None
    company_director_contact: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: str
    alternate_phone: Optional[str] = None
    gstin_status: str = "non-registered"
    gstin: Optional[str] = None
    pan: Optional[str] = None
    business_type: str = "domestic"

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    billing_country: Optional[str] = None
    pincode: Optional[str] = None
    place_of_supply: Optional[str] = None

    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None

    payment_terms_days: int = 30
    currency_code: str = "INR"
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

    @field_validator("gstin_status")
    @classmethod
    def validate_gstin_status(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"registered", "non-registered"}:
            raise ValueError("gstin_status must be 'registered' or 'non-registered'")
        return normalized

    @field_validator("business_type")
    @classmethod
    def validate_business_type(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"domestic", "international"}:
            raise ValueError("business_type must be 'domestic' or 'international'")
        return normalized

    @field_validator("opening_balance_type")
    @classmethod
    def validate_opening_balance_type(cls, value: str) -> str:
        if value not in {"dr", "cr"}:
            raise ValueError("opening_balance_type must be dr or cr")
        return value

    @model_validator(mode="after")
    def validate_gstin_toggle(self):
        if self.gstin_status == "registered" and not self.gstin:
            raise ValueError("GSTIN is required when gstin_status is 'registered'")
        return self


class SupplierCreateRequest(SupplierBase):
    pass


class SupplierUpdateRequest(SupplierBase):
    pass


class SupplierResponse(SupplierBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


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


class SupplierCustomizationOptionsResponse(BaseModel):
    countries: List[str]
    currencies: List[str]
    states: List[str]

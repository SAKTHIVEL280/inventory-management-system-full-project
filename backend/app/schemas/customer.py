"""Customer schemas."""
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, field_validator

GSTIN_REGEX = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"


class CustomerBase(BaseModel):
    customer_code: Optional[str] = None
    company_name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: str
    alternate_phone: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    customer_type: str = "regular"

    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_state_code: Optional[str] = None
    billing_pincode: Optional[str] = None

    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_state_code: Optional[str] = None
    shipping_pincode: Optional[str] = None
    same_as_billing: bool = True

    credit_limit: int = 0
    payment_terms_days: int = 30
    opening_balance: int = 0
    opening_balance_type: str = "dr"
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

    @field_validator("customer_type")
    @classmethod
    def validate_customer_type(cls, value: str) -> str:
        allowed = {"regular", "dealer", "distributor", "retail"}
        if value not in allowed:
            raise ValueError("Invalid customer_type")
        return value

    @field_validator("opening_balance_type")
    @classmethod
    def validate_opening_balance_type(cls, value: str) -> str:
        if value not in {"dr", "cr"}:
            raise ValueError("opening_balance_type must be dr or cr")
        return value


class CustomerCreateRequest(CustomerBase):
    pass


class CustomerUpdateRequest(CustomerBase):
    pass


class CustomerResponse(CustomerBase):
    id: UUID

    class Config:
        from_attributes = True


class CustomerBalanceResponse(BaseModel):
    total_invoiced: int
    total_paid: int
    balance_due: int


class CustomersListResponse(BaseModel):
    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

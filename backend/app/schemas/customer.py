"""Customer schemas."""
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, field_validator, EmailStr

GSTIN_REGEX = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
PAN_REGEX = r"^[A-Z]{5}\d{4}[A-Z]$"
PHONE_REGEX = r"^[6-9]\d{9}$"


class CustomerBase(BaseModel):
    # === Identification ===
    customer_code: Optional[str] = None  # Auto-generated if not provided (e.g., "CUST-00001")
    company_name: str  # REQUIRED: Legal name of the company/customer
    contact_person: Optional[str] = None  # Name of primary contact person
    customer_type: str = "regular"  # REQUIRED: Must be one of ["regular", "dealer", "distributor", "retail"]

    # === Contact Information ===
    phone: str  # REQUIRED: 10-digit Indian mobile number starting with 6-9
    alternate_phone: Optional[str] = None  # Optional secondary phone number
    email: Optional[str] = None  # Optional: Must be valid email format if provided

    # === Tax Identifiers ===
    gstin: Optional[str] = None  # Optional: 15-char GST format (29ABCDE1234F1Z5). Auto-uppercased.
    pan: Optional[str] = None  # Optional: 10-char PAN format (ABCDE1234F). Auto-uppercased.

    # === Billing Address ===
    billing_address_line1: Optional[str] = None  # Street/building address
    billing_address_line2: Optional[str] = None  # Additional address details
    billing_city: Optional[str] = None  # City name
    billing_state: Optional[str] = None  # Full state name (e.g., "Karnataka")
    billing_state_code: Optional[str] = None  # Auto-filled from GSTIN first 2 digits if not provided
    billing_pincode: Optional[str] = None  # 6-digit PIN code

    # === Shipping Address ===
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_state_code: Optional[str] = None
    shipping_pincode: Optional[str] = None
    same_as_billing: bool = True  # If true, shipping address copied from billing

    # === Financial Terms ===
    opening_balance_type: str = "dr"  # REQUIRED: "dr" (debit) or "cr" (credit)
    currency_code: str = "INR"  # Default currency for the customer
    is_active: bool = True  # Set false to soft-deactivate customer

    @field_validator("phone", "alternate_phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        import re
        if not re.match(PHONE_REGEX, value):
            raise ValueError(
                "Invalid phone number. Must be 10 digits starting with 6-9 (e.g., 9000000001)"
            )
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        import re
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, value):
            raise ValueError(
                "Invalid email format (e.g., contact @company.com)"
            )
        return value

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        import re

        upper_value = value.upper()
        if not re.match(GSTIN_REGEX, upper_value):
            raise ValueError(
                "Invalid GSTIN format. Expected: 2 digits + 5 letters + 4 digits + 1 letter + Z + 1 alphanumeric "
                "(e.g., 29ABCDE1234F1Z5)"
            )
        return upper_value

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        import re

        upper_value = value.upper()
        if not re.match(PAN_REGEX, upper_value):
            raise ValueError(
                "Invalid PAN format. Expected: 5 letters + 4 digits + 1 letter (e.g., ABCDE1234F)"
            )
        return upper_value

    @field_validator("customer_type")
    @classmethod
    def validate_customer_type(cls, value: str) -> str:
        allowed = {"regular", "dealer", "distributor", "retail"}
        if value not in allowed:
            raise ValueError(
                f"Invalid customer_type. Must be one of: {', '.join(sorted(allowed))}"
            )
        return value

    @field_validator("opening_balance_type")
    @classmethod
    def validate_opening_balance_type(cls, value: str) -> str:
        if value not in {"dr", "cr"}:
            raise ValueError(
                "opening_balance_type must be 'dr' (debit) or 'cr' (credit)"
            )
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

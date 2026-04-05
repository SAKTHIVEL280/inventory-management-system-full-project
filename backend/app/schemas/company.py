"""Company schemas."""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator

GSTIN_REGEX = r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"


class CompanyBase(BaseModel):
    name: str
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    gstin_status: str = 'non-registered'
    pan: Optional[str] = None
    company_director_name: Optional[str] = None
    company_director_contact: Optional[str] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    pincode: Optional[str] = None

    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None

    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_branch: Optional[str] = None

    invoice_prefix: str = "INV"
    invoice_counter: int = 1
    po_prefix: str = "PO"
    po_counter: int = 1
    so_prefix: str = "SO"
    so_counter: int = 1
    qtn_prefix: str = "QTN"
    qtn_counter: int = 1
    grn_prefix: str = "GRN"
    grn_counter: int = 1

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


class CompanyUpdate(CompanyBase):
    pass


class CompanyResponse(CompanyBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class CompanyLogoResponse(BaseModel):
    logo_url: str


class CompanyBrandingResponse(BaseModel):
    name: str
    logo_url: Optional[str] = None
    logo_data_url: Optional[str] = None

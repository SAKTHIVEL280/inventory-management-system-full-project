"""Proforma Invoice schemas.

Independent replica of the Quotation schemas (app/schemas/sales.py),
renamed to Proforma Invoice. Reuses SalesLineItemRequest for line items.
"""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.schemas.sales import SalesLineItemRequest


class ProformaInvoiceCreateRequest(BaseModel):
    customer_id: UUID
    proforma_date: date
    valid_until: Optional[date] = None
    sold_to_customer_id: Optional[UUID] = None
    bill_to_customer_id: Optional[UUID] = None
    ship_to_customer_id: Optional[UUID] = None
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    status: str = "draft"
    items: List[SalesLineItemRequest]


class ProformaInvoiceStatusRequest(BaseModel):
    status: str


class ProformaInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proforma_number: str
    customer_id: UUID
    proforma_date: Optional[date]
    valid_until: Optional[date]
    status: str
    subtotal: int
    total_discount: int
    total_taxable_amount: int
    total_cgst: int
    total_sgst: int
    total_igst: int
    total_gst: int
    total_amount: int
    notes: Optional[str]
    terms_conditions: Optional[str]
    created_at: Optional[datetime]


class ProformaInvoicesListResponse(BaseModel):
    items: List[ProformaInvoiceResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

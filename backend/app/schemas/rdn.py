"""Return Delivery Note (RDN) schemas."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class RDNLineItemRequest(BaseModel):
    product_id: UUID
    invoice_item_id: UUID
    batch_no: str
    manufacture_date: date
    expiry_date: date
    return_quantity: float
    reason_code: str


class RDNCreateRequest(BaseModel):
    customer_id: UUID
    sales_invoice_id: UUID
    customer_delivery_number: Optional[str] = None
    customer_delivery_date: date
    receipt_date: date
    notes: Optional[str] = None
    items: List[RDNLineItemRequest]


class RDNUpdateRequest(RDNCreateRequest):
    pass


class RDNResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rdn_number: str
    customer_id: UUID
    sales_invoice_id: UUID
    customer_delivery_number: Optional[str] = None
    customer_delivery_date: date
    receipt_date: date
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class RDNListResponse(BaseModel):
    items: List[RDNResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class RDNOverviewItem(BaseModel):
    rdn_id: UUID
    rdn_number: str
    customer_id: UUID
    customer_name: str
    sales_invoice_id: UUID
    invoice_number: str
    receipt_date: date
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    return_quantity: float
    mrp: Optional[int] = None
    status: str


class RDNOverviewResponse(BaseModel):
    items: List[RDNOverviewItem]
    total: int
    page: int
    page_size: int
    has_more: bool

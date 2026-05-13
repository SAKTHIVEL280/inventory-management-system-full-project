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


class RDNCreditNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    credit_note_number: str
    rdn_id: UUID
    sales_invoice_id: UUID
    customer_id: UUID
    credit_note_date: date
    status: str
    subtotal: int
    total_discount: int
    total_taxable_amount: int
    total_cgst: int
    total_sgst: int
    total_igst: int
    total_gst: int
    total_amount: int
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    customer_name: Optional[str] = None
    rdn_created_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class RDNCreditNoteItemResponse(BaseModel):
    id: UUID
    credit_note_id: UUID
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    invoice_item_id: Optional[UUID] = None
    return_quantity: float
    unit_price: int
    mrp: Optional[int] = None
    discount_percent: float
    discount_amount: int
    taxable_amount: int
    gst_rate: int
    cgst_amount: int
    sgst_amount: int
    igst_amount: int
    total_amount: int


class RDNCreditNoteDetailResponse(BaseModel):
    credit_note: RDNCreditNoteResponse
    items: List[RDNCreditNoteItemResponse]


class RDNCreditNoteOverviewItem(BaseModel):
    credit_note_id: UUID
    credit_note_number: str
    rdn_id: UUID
    sales_invoice_id: UUID
    invoice_number: str
    customer_id: UUID
    customer_name: str
    credit_note_date: date
    product_id: UUID
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    mrp: Optional[int] = None
    gst_rate: int
    status: str


class RDNCreditNoteOverviewResponse(BaseModel):
    items: List[RDNCreditNoteOverviewItem]
    total: int
    page: int
    page_size: int
    has_more: bool

"""Sales workflow schemas."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class SalesLineItemRequest(BaseModel):
    product_id: UUID
    description: Optional[str] = None
    quantity: float
    unit_price: int
    discount_percent: float = 0
    gst_rate: int


class QuotationCreateRequest(BaseModel):
    customer_id: UUID
    quotation_date: date
    valid_until: Optional[date] = None
    sold_to_customer_id: Optional[UUID] = None
    bill_to_customer_id: Optional[UUID] = None
    ship_to_customer_id: Optional[UUID] = None
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    status: str = "draft"
    items: List[SalesLineItemRequest]


class QuotationStatusRequest(BaseModel):
    status: str


class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    quotation_number: str
    customer_id: UUID
    quotation_date: Optional[date]
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


class QuotationsListResponse(BaseModel):
    items: List[QuotationResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class SalesOrderCreateRequest(BaseModel):
    customer_id: UUID
    quotation_id: Optional[UUID] = None
    order_date: date
    expected_delivery_date: Optional[date] = None
    sold_to_customer_id: Optional[UUID] = None
    bill_to_customer_id: Optional[UUID] = None
    ship_to_customer_id: Optional[UUID] = None
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    status: str = "draft"
    currency_code: str = "INR"
    exchange_rate: float = 1.0
    items: List[SalesLineItemRequest]


class SalesOrderStatusRequest(BaseModel):
    status: str


class SalesOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    so_number: str
    quotation_id: Optional[UUID]
    customer_id: UUID
    order_date: Optional[date]
    expected_delivery_date: Optional[date]
    status: str
    total_amount: int
    created_at: Optional[datetime]


class SalesOrdersListResponse(BaseModel):
    items: List[SalesOrderResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class SalesInvoiceCreateRequest(BaseModel):
    customer_id: UUID
    sales_order_id: Optional[UUID] = None
    quotation_id: Optional[UUID] = None
    invoice_date: date
    due_date: Optional[date] = None
    sold_to_customer_id: Optional[UUID] = None
    bill_to_customer_id: Optional[UUID] = None
    ship_to_customer_id: Optional[UUID] = None
    supply_state: Optional[str] = None
    supply_state_code: Optional[str] = None
    is_igst: bool = False
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    items: List[SalesLineItemRequest]


class SalesInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    invoice_number: str
    customer_id: UUID
    invoice_date: Optional[date]
    due_date: Optional[date]
    status: str
    total_amount: int
    amount_paid: int
    amount_due: int
    created_at: Optional[datetime]


class SalesInvoicesListResponse(BaseModel):
    items: List[SalesInvoiceResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class SalesReturnLineItemRequest(BaseModel):
    product_id: UUID
    invoice_item_id: Optional[UUID] = None
    quantity: float
    unit_price: int
    gst_rate: int


class SalesReturnCreateRequest(BaseModel):
    invoice_id: UUID
    customer_id: UUID
    return_date: date
    reason: str
    items: List[SalesReturnLineItemRequest]

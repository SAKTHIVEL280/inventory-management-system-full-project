"""Sales workflow schemas."""
from datetime import date
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


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
    items: List[SalesLineItemRequest]


class SalesOrderStatusRequest(BaseModel):
    status: str


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

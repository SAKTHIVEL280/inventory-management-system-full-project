"""Purchase workflow schemas."""
from typing import List, Optional
from uuid import UUID
from datetime import date
from pydantic import BaseModel


class PurchaseLineItemRequest(BaseModel):
    product_id: UUID
    description: Optional[str] = None
    batch_no: Optional[str] = None
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quantity: float
    free_quantity: float = 0
    unit_price: int
    discount_percent: float = 0
    gst_rate: int
    purchase_order_item_id: Optional[UUID] = None


class PurchaseOrderCreateRequest(BaseModel):
    supplier_id: UUID
    order_date: date
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    status: str = "draft"
    currency_code: str = "INR"
    exchange_rate: float = 1.0
    items: List[PurchaseLineItemRequest]


class PurchaseOrderStatusRequest(BaseModel):
    status: str


class GRNCreateRequest(BaseModel):
    supplier_id: UUID
    purchase_order_id: Optional[UUID] = None
    supplier_invoice_number: Optional[str] = None
    supplier_invoice_date: Optional[date] = None
    receipt_date: date
    notes: Optional[str] = None
    items: List[PurchaseLineItemRequest]


class PurchaseReturnLineItemRequest(BaseModel):
    product_id: UUID
    grn_item_id: Optional[UUID] = None
    quantity: float
    unit_price: int
    gst_rate: int


class PurchaseReturnCreateRequest(BaseModel):
    supplier_id: UUID
    grn_id: UUID
    return_date: date
    reason: str
    items: List[PurchaseReturnLineItemRequest]


class PurchaseReturnStatusRequest(BaseModel):
    status: str

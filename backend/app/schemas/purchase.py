"""Purchase workflow schemas."""
from typing import List, Optional
from uuid import UUID
from datetime import date
from pydantic import BaseModel, Field, model_validator


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
    under_delivery_tolerance: Optional[float] = Field(default=0, ge=0)
    over_delivery_tolerance: Optional[float] = Field(default=0, ge=0)
    items: List[PurchaseLineItemRequest]

    @model_validator(mode="after")
    def validate_tolerance_range(self):
        self.under_delivery_tolerance = float(self.under_delivery_tolerance or 0)
        self.over_delivery_tolerance = float(self.over_delivery_tolerance or 0)
        if self.under_delivery_tolerance > self.over_delivery_tolerance:
            raise ValueError("Under Delivery Tolerance must be less than or equal to Over Delivery Tolerance")
        return self


class PurchaseOrderStatusRequest(BaseModel):
    status: str


class GRNCreateRequest(BaseModel):
    supplier_id: UUID
    purchase_order_id: Optional[UUID] = None
    supplier_invoice_number: Optional[str] = None
    supplier_invoice_date: Optional[date] = None
    receipt_date: date
    notes: Optional[str] = None
    under_delivery_tolerance: Optional[float] = Field(default=0, ge=0)
    over_delivery_tolerance: Optional[float] = Field(default=0, ge=0)
    items: List[PurchaseLineItemRequest]

    @model_validator(mode="after")
    def validate_tolerance_range(self):
        self.under_delivery_tolerance = float(self.under_delivery_tolerance or 0)
        self.over_delivery_tolerance = float(self.over_delivery_tolerance or 0)
        if self.under_delivery_tolerance > self.over_delivery_tolerance:
            raise ValueError("Under Delivery Tolerance must be less than or equal to Over Delivery Tolerance")
        return self


class GRNReverseRequest(BaseModel):
    """MCN-BUG-004: mandatory reason captured when reversing a confirmed GRN."""
    reason: str

    @model_validator(mode="after")
    def _validate_reason(self):
        if not (self.reason or "").strip():
            raise ValueError("A reversal reason is required")
        return self


class GRNConfirmedEditItem(BaseModel):
    """MCN-BUG-004-ii: a single editable GRN line for a confirmed GRN.

    Identified by the existing grn_items.id. Only the detail fields permitted by
    the BRD are accepted; product mapping and PO linkage are not changed here.
    """
    id: UUID
    batch_no: Optional[str] = None
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quantity: float
    free_quantity: float = 0
    unit_price: int


class GRNConfirmedEditRequest(BaseModel):
    """MCN-BUG-004-ii: edit detail fields of an already-confirmed GRN.

    Stock and totals are reconciled by the delta between old and new values.
    """
    notes: Optional[str] = None
    items: List[GRNConfirmedEditItem]


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

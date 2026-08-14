"""Sales workflow schemas."""
from datetime import date, datetime
from typing import List, Optional, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.utils.quantity_validation import validate_whole_quantity


InvoiceTypeLiteral = Literal[
    "export_invoice",
    "within_state",
    "other_states",
    "union_territory",
]


class SalesLineItemRequest(BaseModel):
    product_id: UUID
    description: Optional[str] = None
    order_unit: Optional[str] = None
    batch_no: Optional[str] = None
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quantity: float
    free_quantity: float = 0
    unit_price: int
    discount_percent: float = 0
    gst_rate: int

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, value):
        return validate_whole_quantity(value, "Quantity")

    @field_validator("free_quantity")
    @classmethod
    def _validate_free_quantity(cls, value):
        return validate_whole_quantity(value, "Free quantity")


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
    invoice_type: Optional[InvoiceTypeLiteral] = None
    import_export_code: Optional[str] = None
    is_igst: bool = False
    # Enhancement 3: mandatory internal fields (validated in the router so the
    # message is field-specific and consistent with the frontend).
    stockist_name: Optional[str] = None
    stockist_city: Optional[str] = None
    sales_manager_name: Optional[str] = None
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    # Multi-currency: the transaction currency is authoritative from the customer
    # (server-side); the client sends the exchange rate to base (INR) for foreign
    # invoices. Must be > 0 when provided; ignored (forced to 1.0) for INR invoices.
    currency_code: Optional[str] = None
    exchange_rate: Optional[float] = None
    items: List[SalesLineItemRequest]

    @field_validator("exchange_rate")
    @classmethod
    def _validate_exchange_rate(cls, value):
        if value is None:
            return value
        if value <= 0:
            raise ValueError("Exchange rate must be greater than zero")
        return value


class SalesInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    invoice_number: str
    customer_id: UUID
    # Snapshot of the customer name/code resolved at read time. Populated even when
    # the customer has since been soft-deleted, so historical invoices always show
    # the original customer instead of "Unknown customer".
    customer_name: Optional[str] = None
    customer_code: Optional[str] = None
    invoice_date: Optional[date]
    due_date: Optional[date]
    invoice_type: InvoiceTypeLiteral
    import_export_code: Optional[str] = None
    status: str
    stockist_name: Optional[str] = None
    stockist_city: Optional[str] = None
    sales_manager_name: Optional[str] = None
    total_amount: int
    amount_paid: int
    amount_due: int
    # Multi-currency: transaction currency + rate to base (INR). base_currency_total
    # is the INR equivalent of total_amount (= total_amount * exchange_rate).
    currency_code: str = "INR"
    exchange_rate: float = 1.0
    base_currency: str = "INR"
    base_currency_total: Optional[int] = None
    created_at: Optional[datetime]

    @model_validator(mode="after")
    def _compute_base_currency_total(self):
        # INR (base) equivalent of the grand total, using the invoice's stored rate.
        self.base_currency = "INR"
        if self.base_currency_total is None:
            self.base_currency_total = int(round(int(self.total_amount or 0) * float(self.exchange_rate or 1)))
        return self


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

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, value):
        return validate_whole_quantity(value, "Return quantity")


class SalesReturnCreateRequest(BaseModel):
    invoice_id: UUID
    customer_id: UUID
    return_date: date
    reason: str
    items: List[SalesReturnLineItemRequest]

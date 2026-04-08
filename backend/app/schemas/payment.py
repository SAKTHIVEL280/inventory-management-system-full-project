"""Payment workflow schemas."""
from datetime import date
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class PaymentAllocationRequest(BaseModel):
    invoice_id: Optional[UUID] = None
    purchase_grn_id: Optional[UUID] = None
    allocated_amount: int


class PaymentCreateRequest(BaseModel):
    payment_type: str
    party_type: str
    customer_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    purchase_order_id: Optional[UUID] = None
    payment_date: date
    amount: int
    payment_mode: str
    reference_number: Optional[str] = None
    cheque_date: Optional[date] = None
    bank_name: Optional[str] = None
    notes: Optional[str] = None
    allocations: List[PaymentAllocationRequest] = []


class PaymentStatusRequest(BaseModel):
    status: str

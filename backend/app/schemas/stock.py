"""Stock module schemas."""
from datetime import date
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from uuid import UUID


class InventoryCountItemCreateRequest(BaseModel):
    serial_number: int
    product_id: UUID
    product_description: Optional[str] = None
    quantity: float
    batch_no: Optional[str] = None
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None

    @field_validator("serial_number")
    @classmethod
    def validate_serial_number(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("serial_number must be greater than zero")
        return value

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: float) -> float:
        if value < 0:
            raise ValueError("quantity cannot be negative")
        return value


class InventoryCountCreateRequest(BaseModel):
    count_date: date
    count_performed_by: str
    items: list[InventoryCountItemCreateRequest]

    @field_validator("count_performed_by")
    @classmethod
    def validate_count_performed_by(cls, value: str) -> str:
        token = (value or "").strip()
        if not token:
            raise ValueError("count_performed_by is required")
        return token


class InventoryCountItemResponse(BaseModel):
    serial_number: int
    product_id: str
    product_description: Optional[str] = None
    quantity: float
    batch_no: Optional[str] = None
    manufacture_date: Optional[str] = None
    expiry_date: Optional[str] = None


class InventoryCountResponse(BaseModel):
    id: str
    count_number: str
    count_date: str
    count_performed_by: str
    status: str
    items: list[InventoryCountItemResponse]

    model_config = ConfigDict(from_attributes=True)


class InventoryCountDifferenceItemResponse(BaseModel):
    serial_number: int
    product_id: str
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    batch_no: Optional[str] = None
    manufacture_date: Optional[str] = None
    expiry_date: Optional[str] = None
    counted_quantity: float
    existing_stock: float
    difference: float


class InventoryCountDifferenceResponse(BaseModel):
    count_number: str
    count_date: str
    count_performed_by: str
    total_items: int
    items: list[InventoryCountDifferenceItemResponse]
"""Product schemas."""
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, field_validator


class ProductCategoryCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class ProductCategoryResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class UnitOfMeasureResponse(BaseModel):
    id: UUID
    name: str
    abbreviation: str
    is_active: bool

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    product_code: Optional[str] = None
    sku: Optional[str] = None
    name: str
    description: Optional[str] = None
    category_id: UUID
    uom_id: UUID
    alt_uom_id: Optional[UUID] = None
    alt_uom_conversion: Optional[Decimal] = None
    hsn_code: str
    gst_rate: int
    purchase_price: int = 0
    selling_price: int = 0
    mrp: int = 0
    minimum_stock: int = 0
    opening_stock: int = 0
    is_active: bool = True

    @field_validator("gst_rate")
    @classmethod
    def validate_gst_rate(cls, value: int) -> int:
        if value not in {0, 5, 12, 18, 28}:
            raise ValueError("gst_rate must be one of 0,5,12,18,28")
        return value

    @field_validator("hsn_code")
    @classmethod
    def validate_hsn_code(cls, value: str) -> str:
        if not value.isdigit() or len(value) not in {6, 7, 8}:
            raise ValueError("hsn_code must be a 6-8 digit numeric string")
        return value


class ProductCreateRequest(ProductBase):
    pass


class ProductUpdateRequest(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: UUID

    class Config:
        from_attributes = True


class ProductWithStockResponse(ProductResponse):
    current_stock: float = 0
    low_stock: bool = False


class ProductsListResponse(BaseModel):
    items: List[ProductWithStockResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

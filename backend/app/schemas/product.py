"""Product schemas."""
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductCategoryCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class ProductCategoryResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UnitOfMeasureResponse(BaseModel):
    id: UUID
    name: str
    abbreviation: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    product_code: Optional[str] = None
    sku: Optional[str] = None
    name: str
    description: Optional[str] = None
    category_id: UUID
    uom_id: Optional[UUID] = None
    alt_uom_id: Optional[UUID] = None
    alt_uom_conversion: Optional[Decimal] = None
    hsn_code: str
    gst_rate: int
    purchase_price: int = 0
    selling_price: int = 0
    mrp: int = 0
    minimum_stock: int = 0
    safety_stock: int = 0
    opening_stock: int = 0
    status: str = 'active'
    is_active: bool = True

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"active", "inactive", "flagged_for_deletion"}
        if value not in allowed:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
        return value

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
    @model_validator(mode="after")
    def validate_price_hierarchy(self):
        if not self.sku or not self.sku.strip():
            raise ValueError("Base Unit is required")
        self.sku = self.sku.strip()
        if self.purchase_price >= self.selling_price:
            raise ValueError("Purchase price must be less than Selling Price")
        if self.selling_price >= self.mrp:
            raise ValueError("Selling Price must be less than MRP")
        return self


class ProductUpdateRequest(ProductBase):
    @model_validator(mode="after")
    def validate_price_hierarchy(self):
        if not self.sku or not self.sku.strip():
            raise ValueError("Base Unit is required")
        self.sku = self.sku.strip()
        if self.purchase_price >= self.selling_price:
            raise ValueError("Purchase price must be less than Selling Price")
        if self.selling_price >= self.mrp:
            raise ValueError("Selling Price must be less than MRP")
        return self


class ProductResponse(ProductBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class ProductWithStockResponse(ProductResponse):
    current_stock: float = 0
    safety_stock: int = 0
    low_stock: bool = False
    below_safety_stock: bool = False


class ProductsListResponse(BaseModel):
    items: List[ProductWithStockResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ProductListQueryParams(BaseModel):
    search: Optional[str] = Field(default=None, max_length=100)
    category_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    all_products: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)


class StockAdjustmentRequest(BaseModel):
    product_id: UUID
    quantity: float  # Positive for add, negative for remove
    notes: Optional[str] = None


class StockLedgerResponse(BaseModel):
    id: str
    product_id: str
    transaction_type: str
    reference_type: Optional[str] = None
    reference_number: Optional[str] = None
    quantity: float
    rate: float
    transaction_date: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

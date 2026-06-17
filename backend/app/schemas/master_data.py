"""Sales master-data schemas (Stockist, Sales Manager).

Enhancement 3 — masters managed under Customization (FR-15, FR-16, FR-20).
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Stockist ─────────────────────────────────────────────────────────────────
class StockistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    city: Optional[str] = Field(default=None, max_length=120)
    is_active: bool = True


class StockistUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    city: Optional[str] = Field(default=None, max_length=120)
    is_active: Optional[bool] = None


class StockistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    city: Optional[str] = None
    is_active: bool
    is_deleted: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StockistsListResponse(BaseModel):
    items: List[StockistResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ── Sales Manager ────────────────────────────────────────────────────────────
class SalesManagerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    employee_id: Optional[str] = Field(default=None, max_length=50)
    region: Optional[str] = Field(default=None, max_length=120)
    is_active: bool = True


class SalesManagerUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    employee_id: Optional[str] = Field(default=None, max_length=50)
    region: Optional[str] = Field(default=None, max_length=120)
    is_active: Optional[bool] = None


class SalesManagerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    employee_id: Optional[str] = None
    region: Optional[str] = None
    is_active: bool
    is_deleted: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SalesManagersListResponse(BaseModel):
    items: List[SalesManagerResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

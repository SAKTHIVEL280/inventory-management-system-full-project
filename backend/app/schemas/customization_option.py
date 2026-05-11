"""Customization option schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomizationOptionCreateRequest(BaseModel):
    module: str = Field(..., min_length=1, max_length=50)
    field_name: str = Field(..., min_length=1, max_length=50)
    option_value: str = Field(..., min_length=1, max_length=120)
    display_label: Optional[str] = Field(default=None, max_length=150)
    sort_order: int = 0
    is_active: bool = True


class CustomizationOptionUpdateRequest(BaseModel):
    module: Optional[str] = Field(default=None, min_length=1, max_length=50)
    field_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    option_value: Optional[str] = Field(default=None, min_length=1, max_length=120)
    display_label: Optional[str] = Field(default=None, max_length=150)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CustomizationOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    module: str
    field_name: str
    option_value: str
    display_label: Optional[str] = None
    sort_order: int
    is_active: bool
    is_deleted: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomizationOptionsListResponse(BaseModel):
    items: List[CustomizationOptionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

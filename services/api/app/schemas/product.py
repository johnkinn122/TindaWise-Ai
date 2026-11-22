import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.category import CategoryRead
from app.schemas.common import ORMModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Sku = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16)]
# Money: exact decimals with two places, never floats. Serialized as strings in JSON.
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]


class _ProductFields(BaseModel):
    @field_validator("barcode", mode="before", check_fields=False)
    @classmethod
    def blank_barcode_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class ProductCreate(_ProductFields):
    name: Name
    sku: Sku
    barcode: str | None = Field(default=None, max_length=64)
    category_id: uuid.UUID | None = None
    unit: Unit = "pcs"
    price: Money
    cost: Money = Decimal("0")
    reorder_level: int = Field(default=0, ge=0, le=1_000_000)
    initial_stock: int = Field(default=0, ge=0, le=1_000_000)


class ProductUpdate(_ProductFields):
    """Partial update. Stock is not editable here: use a stock adjustment, so it is recorded."""

    name: Name | None = None
    sku: Sku | None = None
    barcode: str | None = Field(default=None, max_length=64)
    category_id: uuid.UUID | None = None
    unit: Unit | None = None
    price: Money | None = None
    cost: Money | None = None
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)
    is_active: bool | None = None


class ProductRead(ORMModel):
    id: uuid.UUID
    name: str
    sku: str
    barcode: str | None
    category: CategoryRead | None
    unit: str
    price: Decimal
    # Null for roles that may not see costs (cashiers); see api/deps.can_see_costs.
    cost: Decimal | None
    currency: str
    stock_on_hand: int
    reorder_level: int
    stock_status: StockStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


ProductSort = Literal["name", "-name", "stock", "-stock", "price", "-price", "-updated"]

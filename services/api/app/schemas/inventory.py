import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.stock_movement import MovementReason
from app.schemas.common import ORMModel


class StockAdjustmentCreate(BaseModel):
    quantity_change: int = Field(ge=-1_000_000, le=1_000_000)
    reason: MovementReason
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=280)] | None = None

    @model_validator(mode="after")
    def check_direction(self) -> "StockAdjustmentCreate":
        if self.quantity_change == 0:
            raise ValueError("quantity_change cannot be zero")
        if self.reason == MovementReason.INITIAL:
            raise ValueError("'initial' is set automatically when a product is created")
        must_add = {MovementReason.PURCHASE, MovementReason.RETURN}
        must_remove = {MovementReason.SALE, MovementReason.DAMAGE}
        if self.reason in must_add and self.quantity_change < 0:
            raise ValueError(f"'{self.reason}' must add stock (positive quantity)")
        if self.reason in must_remove and self.quantity_change > 0:
            raise ValueError(f"'{self.reason}' must remove stock (negative quantity)")
        return self


class StockMovementRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity_change: int
    balance_after: int
    reason: MovementReason
    note: str | None
    created_at: datetime


# ── Store-wide ledger (GET /inventory/...) ──────────────────────────────────

SourceKind = Literal["sale", "refund", "purchase_order"]


class MovementSource(BaseModel):
    """What caused a movement, so the page can link to it. `id` is the page to open: the sale for
    a sale or a refund (refunds are shown on their receipt), the order for a delivery."""

    kind: SourceKind
    id: uuid.UUID
    code: str  # S-000123, R-000007 or PO-000004


class LedgerEntry(BaseModel):
    id: uuid.UUID
    created_at: datetime
    product_id: uuid.UUID
    product_name: str
    sku: str
    unit: str
    quantity_change: int
    balance_after: int
    reason: MovementReason
    note: str | None
    created_by_name: str | None  # null for rows recorded before sign-in existed
    source: MovementSource | None


class Person(BaseModel):
    id: uuid.UUID
    name: str


class InventorySummary(BaseModel):
    """Active products only: archived products are off the shelf even if they have stock."""

    products: int
    units_on_hand: int
    stock_value: Decimal  # units on hand x each product's current cost
    currency: str
    low_stock: int  # 1 .. reorder level
    out_of_stock: int  # 0
    people: list[Person]  # members who have changed stock here, for the ledger's "who" filter

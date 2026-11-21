import uuid
from datetime import datetime
from typing import Annotated

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

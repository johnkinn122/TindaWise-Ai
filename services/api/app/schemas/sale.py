import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, computed_field, model_validator

from app.schemas.common import ORMModel


class SaleLineCreate(BaseModel):
    """The client sends only what and how many. Prices come from the database."""

    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=10_000)


class SaleCreate(BaseModel):
    lines: list[SaleLineCreate] = Field(min_length=1, max_length=200)
    payment_method: Literal["cash", "e_wallet"]
    amount_tendered: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = None
    payment_reference: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None

    @model_validator(mode="after")
    def check_payment(self) -> "SaleCreate":
        if self.payment_method == "cash" and self.amount_tendered is None:
            raise ValueError("Enter the cash received")
        if self.payment_method == "e_wallet" and not self.payment_reference:
            raise ValueError("Enter the e-wallet reference number")
        return self


class SaleLineRead(ORMModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    unit: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class SaleRead(ORMModel):
    id: uuid.UUID
    receipt_number: int
    total: Decimal
    currency: str
    payment_method: str
    amount_tendered: Decimal | None
    change_due: Decimal | None
    payment_reference: str | None
    created_at: datetime
    cashier_name: str | None = None
    lines: list[SaleLineRead]

    @computed_field
    @property
    def receipt_code(self) -> str:
        return f"S-{self.receipt_number:06d}"

    @computed_field
    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)


class SaleSummary(ORMModel):
    id: uuid.UUID
    receipt_number: int
    total: Decimal
    payment_method: str
    created_at: datetime
    cashier_name: str | None = None
    item_count: int

    @computed_field
    @property
    def receipt_code(self) -> str:
        return f"S-{self.receipt_number:06d}"

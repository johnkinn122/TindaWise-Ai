import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, computed_field, field_validator

from app.schemas.common import ORMModel

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Quantity = Annotated[int, Field(ge=1, le=1_000_000)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

PurchaseOrderStatusName = Literal[
    "draft", "approved", "partially_received", "received", "closed", "cancelled"
]


class PurchaseOrderLineInput(BaseModel):
    product_id: uuid.UUID
    quantity: Quantity
    # Omit to use the product's current cost.
    unit_cost: Money | None = None


class _DraftFields(BaseModel):
    supplier_id: uuid.UUID | None = None
    expected_on: date | None = None
    notes: Notes | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def blank_notes_are_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class PurchaseOrderCreate(_DraftFields):
    lines: list[PurchaseOrderLineInput] = Field(min_length=1, max_length=200)


class PurchaseOrderUpdate(_DraftFields):
    """Drafts only. Fields that are sent replace the old values; `lines` replaces all lines."""

    lines: list[PurchaseOrderLineInput] | None = Field(default=None, min_length=1, max_length=200)


class ReceiveLineInput(BaseModel):
    line_id: uuid.UUID
    quantity: Annotated[int, Field(ge=0, le=1_000_000)]


class ReceiveInput(BaseModel):
    """Quantities that arrived in this delivery. Lines left out (or 0) received nothing."""

    lines: list[ReceiveLineInput] = Field(min_length=1, max_length=200)
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=280)] | None = None


class SupplierBrief(ORMModel):
    id: uuid.UUID
    name: str
    is_active: bool


class PurchaseOrderLineRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    sku: str
    unit: str
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal
    line_total: Decimal

    @computed_field
    @property
    def quantity_remaining(self) -> int:
        return self.quantity_ordered - self.quantity_received


class ReceiptLineRead(BaseModel):
    product_id: uuid.UUID
    product_name: str
    quantity: int


class PurchaseOrderReceiptRead(BaseModel):
    id: uuid.UUID
    note: str | None
    created_at: datetime
    received_by: str | None
    lines: list[ReceiptLineRead]


class PurchaseOrderEvent(BaseModel):
    """One line of the order's history, oldest first."""

    action: Literal["created", "approved", "received", "closed", "cancelled"]
    at: datetime
    by: str | None


class PurchaseOrderSummary(BaseModel):
    id: uuid.UUID
    code: str
    status: PurchaseOrderStatusName
    supplier: SupplierBrief | None
    total: Decimal
    currency: str
    line_count: int
    expected_on: date | None
    created_at: datetime


class PurchaseOrderRead(PurchaseOrderSummary):
    notes: str | None
    lines: list[PurchaseOrderLineRead]
    receipts: list[PurchaseOrderReceiptRead]
    history: list[PurchaseOrderEvent]
    updated_at: datetime

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


class PaymentMethod(enum.StrEnum):
    CASH = "cash"
    E_WALLET = "e_wallet"  # GCash, Maya: recorded by reference number, not processed here


class Sale(UUIDPrimaryKeyMixin, Base):
    """A completed checkout. Totals are computed on the server from database prices."""

    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("organization_id", "receipt_number"),
        # Same Idempotency-Key = the same checkout retried; it must never record twice.
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint("payment_method IN ('cash','e_wallet')", name="payment_method_valid"),
        CheckConstraint(
            "payment_method <> 'cash' OR (amount_tendered >= total AND change_due >= 0)",
            name="cash_covers_total",
        ),
        Index("ix_sales_organization_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    receipt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_tendered: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    change_due: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list["SaleLine"]] = relationship(
        back_populates="sale", order_by="SaleLine.position", lazy="selectin"
    )

    @property
    def receipt_code(self) -> str:
        return f"S-{self.receipt_number:06d}"


class SaleLine(UUIDPrimaryKeyMixin, Base):
    """One product on a receipt. Name, price and cost are copied at the moment of sale, so old
    receipts and profit figures stay correct after prices change."""

    __tablename__ = "sale_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("line_total = unit_price * quantity", name="line_total_matches"),
        UniqueConstraint("sale_id", "position"),
    )

    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="lines")

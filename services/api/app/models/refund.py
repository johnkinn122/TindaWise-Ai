import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
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
from app.models.sale import SaleLine


class RefundReason(enum.StrEnum):
    CUSTOMER_RETURN = "customer_return"  # returned unused, changed their mind
    DAMAGED = "damaged"  # defective, spoiled or expired
    WRONG_ITEM = "wrong_item"  # rung up the wrong item or quantity
    OTHER = "other"  # a note is required


class Refund(UUIDPrimaryKeyMixin, Base):
    """Money given back on a sale. The sale itself is never edited; a receipt can have several
    refunds (partial refunds) until every unit on it has been refunded.

    The money goes back the way it was paid (`payment_method` is copied from the sale).
    `restocked_cost` is the cost of the units put back on the shelf: those units are inventory
    again, so their cost no longer counts against profit. Units not restocked stay a loss.
    """

    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("organization_id", "refund_number"),
        # Same Idempotency-Key = the same refund retried; it must never pay out twice.
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint("restocked_cost >= 0", name="restocked_cost_non_negative"),
        CheckConstraint(
            "reason IN ('customer_return','damaged','wrong_item','other')", name="reason_valid"
        ),
        CheckConstraint("reason <> 'other' OR note IS NOT NULL", name="other_needs_note"),
        Index("ix_refunds_organization_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refund_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    restocked_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list["RefundLine"]] = relationship(
        back_populates="refund", order_by="RefundLine.position", lazy="selectin"
    )

    @property
    def refund_code(self) -> str:
        return f"R-{self.refund_number:06d}"


class RefundLine(UUIDPrimaryKeyMixin, Base):
    """Units of one receipt line given back. Price and cost are copied from that receipt line,
    so a refund pays back exactly what was charged, whatever the product costs today."""

    __tablename__ = "refund_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("line_total = unit_price * quantity", name="line_total_matches"),
        UniqueConstraint("refund_id", "sale_line_id"),
    )

    refund_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sale_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sale_lines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # the receipt line's position
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # True = put back on the shelf (stock goes up). False = damaged or spoiled, stock unchanged.
    restocked: Mapped[bool] = mapped_column(Boolean, nullable=False)

    refund: Mapped[Refund] = relationship(back_populates="lines")
    sale_line: Mapped[SaleLine] = relationship(lazy="joined")

    @property
    def product_name(self) -> str:
        return self.sale_line.product_name

    @property
    def unit(self) -> str:
        return self.sale_line.unit

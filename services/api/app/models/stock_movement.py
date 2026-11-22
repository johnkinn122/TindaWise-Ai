import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class MovementReason(enum.StrEnum):
    INITIAL = "initial"  # opening stock when a product is created
    PURCHASE = "purchase"  # received from a supplier
    SALE = "sale"  # sold at the counter
    RETURN = "return"  # customer returned an item
    DAMAGE = "damage"  # spoiled, broken, expired
    ADJUSTMENT = "adjustment"  # stock count correction


class StockMovement(UUIDPrimaryKeyMixin, Base):
    """Append-only inventory ledger. Rows are never updated or deleted.

    `balance_after` records the stock level right after this movement, so the history can be
    audited without replaying every row.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity_change <> 0", name="quantity_change_non_zero"),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        CheckConstraint(
            "reason IN ('initial','purchase','sale','return','damage','adjustment')",
            name="reason_valid",
        ),
        # Same Idempotency-Key twice = same request retried; the second one must not apply.
        UniqueConstraint("organization_id", "idempotency_key"),
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # The receipt this movement belongs to, when it came from a sale.
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The delivery this movement belongs to, when stock was received on a purchase order.
    purchase_order_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_order_receipts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Who made the change (audit trail). Null for rows recorded before sign-in existed.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

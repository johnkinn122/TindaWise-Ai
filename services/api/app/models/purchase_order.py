import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
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

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.supplier import Supplier


class PurchaseOrderStatus(enum.StrEnum):
    """draft → approved → (partially_received →) received, or closed short / cancelled.

    - draft: editable by owners and managers. Supplier may still be empty.
    - approved: the owner agreed to the spend. Lines are locked.
    - partially_received / received: stock has come in against it.
    - closed: some items will never arrive; the rest was received.
    - cancelled: nothing was received and nothing will be.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An order to a supplier. Every change of status records who did it and when."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "po_number"),
        # Same Idempotency-Key = the same "create" retried; it must never create two drafts.
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint(
            "status IN ('draft','approved','partially_received','received','closed','cancelled')",
            name="status_valid",
        ),
        # A supplier is required from approval on (a draft cancelled early may have none).
        CheckConstraint(
            "status IN ('draft','cancelled') OR supplier_id IS NOT NULL",
            name="supplier_after_draft",
        ),
        CheckConstraint(
            "status IN ('draft','cancelled') OR approved_at IS NOT NULL", name="approved_recorded"
        ),
        Index("ix_purchase_orders_organization_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    po_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    expected_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when the order is finished: fully received, closed short, or cancelled.
    finished_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    supplier: Mapped[Supplier | None] = relationship(lazy="joined")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order",
        order_by="PurchaseOrderLine.position",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    receipts: Mapped[list["PurchaseOrderReceipt"]] = relationship(
        order_by="PurchaseOrderReceipt.created_at", lazy="selectin"
    )

    @property
    def code(self) -> str:
        return f"PO-{self.po_number:06d}"


class PurchaseOrderLine(UUIDPrimaryKeyMixin, Base):
    """One product on an order. Name, SKU and unit are copied when the line is written, so the
    order reads the same after a product is renamed."""

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="quantity_ordered_positive"),
        CheckConstraint(
            "quantity_received >= 0 AND quantity_received <= quantity_ordered",
            name="quantity_received_in_range",
        ),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("line_total = unit_cost * quantity_ordered", name="line_total_matches"),
        UniqueConstraint("purchase_order_id", "position"),
        UniqueConstraint("purchase_order_id", "product_id"),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class PurchaseOrderReceipt(UUIDPrimaryKeyMixin, Base):
    """One delivery received against an order. Its stock movements carry its id, so the ledger
    shows exactly what arrived in each delivery."""

    __tablename__ = "purchase_order_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

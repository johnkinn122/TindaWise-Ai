import uuid
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.category import Category


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A sellable item.

    `stock_on_hand` is a cached balance. The source of truth for *how* it got there is the
    append-only `stock_movements` ledger; both are always written in the same transaction.
    Quantities are whole units for now (no fractional kilos yet).
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku"),
        # Barcode is optional, but when present it must be unique within the organization.
        Index(
            "uq_products_organization_id_barcode",
            "organization_id",
            "barcode",
            unique=True,
            postgresql_where=text("barcode IS NOT NULL"),
        ),
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("cost >= 0", name="cost_non_negative"),
        CheckConstraint("stock_on_hand >= 0", name="stock_non_negative"),
        CheckConstraint("reorder_level >= 0", name="reorder_level_non_negative"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="pcs")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="PHP")
    stock_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[Category | None] = relationship(lazy="joined")

    @property
    def stock_status(self) -> str:
        if self.stock_on_hand == 0:
            return "out_of_stock"
        if self.stock_on_hand <= self.reorder_level:
            return "low_stock"
        return "in_stock"

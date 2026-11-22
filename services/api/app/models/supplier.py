import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Someone the store buys from. Archived, never deleted, so old purchase orders keep it."""

    __tablename__ = "suppliers"
    __table_args__ = (
        # "Puregold" and "puregold " are the same supplier within one store.
        Index(
            "uq_suppliers_organization_id_lower_name",
            "organization_id",
            text("lower(name)"),
            unique=True,
        ),
        CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days BETWEEN 0 AND 60",
            name="lead_time_days_range",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Days from placing an order to it arriving. None: use the store's default.
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

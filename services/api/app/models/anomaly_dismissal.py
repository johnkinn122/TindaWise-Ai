import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class AnomalyDismissal(UUIDPrimaryKeyMixin, Base):
    """Someone looked at a "Worth a look" alert and set it aside.

    Alerts themselves aren't stored: they're recomputed from sales and the stock ledger each
    time (`services/anomalies.py`), so they always match the records. Only the decision to
    dismiss one is kept, keyed by what identifies an alert: product, store day and kind.

    Kinds: "spike" and "drop" (an unusual sales day; `day` is that day) and "shrinkage" (stock
    going missing; `day` is the latest count that found stock missing, so the alert comes back
    only when a later count finds more).
    """

    __tablename__ = "anomaly_dismissals"
    __table_args__ = (
        # One dismissal per alert. Dismissing twice returns the first one.
        UniqueConstraint("organization_id", "product_id", "day", "kind"),
        CheckConstraint("kind IN ('spike', 'drop', 'shrinkage')", name="kind_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)  # store-local day of the alert
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    dismissed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

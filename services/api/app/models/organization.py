from sqlalchemy import CHAR, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A business (one store or a group of stores). Every business record belongs to one."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="PHP")
    # IANA time zone name. Decides where "today" starts and ends for this store's reports.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Manila", server_default="Asia/Manila"
    )
    # Last receipt number used. Incremented under a row lock when a sale is recorded, so
    # numbers are sequential per store with no gaps from concurrent sales.
    last_receipt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Last purchase order number used; same locking rule as receipts.
    last_po_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Last refund number used; same locking rule as receipts.
    last_refund_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

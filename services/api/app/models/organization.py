from sqlalchemy import CHAR, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A business (one store or a group of stores). Every business record belongs to one."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="PHP")

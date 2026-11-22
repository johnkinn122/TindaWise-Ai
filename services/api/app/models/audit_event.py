import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class AuditAction(enum.StrEnum):
    """Sensitive operations that leave an audit record. Stock changes aren't here: the
    `stock_movements` ledger already records every one with who made it."""

    STORE_UPDATED = "store.updated"
    MEMBER_ADDED = "member.added"
    REFUND_CREATED = "refund.created"
    PURCHASE_ORDER_APPROVED = "purchase_order.approved"
    PURCHASE_ORDER_CANCELLED = "purchase_order.cancelled"
    PURCHASE_ORDER_CLOSED = "purchase_order.closed"
    PRODUCT_PRICE_CHANGED = "product.price_changed"
    PRODUCT_ARCHIVED = "product.archived"


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Who did what, to which record, and when. Append-only: a database trigger rejects every
    UPDATE and DELETE (see the migration), so not even the application can rewrite history.

    Written in the same transaction as the change it describes, so a change never happens
    without its record and a rolled-back change leaves none.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        # The activity log: newest first, optionally within a date range.
        Index("ix_audit_events_organization_created", "organization_id", "created_at"),
    )

    # RESTRICT, not CASCADE or SET NULL: deleting a store or person must not erase or rewrite
    # the trail (and the trigger would refuse those writes anyway). Both are archived, never
    # deleted, in this app.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    # Null is reserved for actions without a signed-in person (e.g. a future scheduled job).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    summary: Mapped[str] = mapped_column(String(280), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

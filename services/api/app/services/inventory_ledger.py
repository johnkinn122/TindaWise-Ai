"""Store-wide inventory views: the ledger of every stock movement, and a stock summary.

Read-only. Every stock change is written by `app.services.inventory.record_movement`; this module
only reads `stock_movements` and the records each movement points to (sale, refund, delivery).

- Dates are store days in the organization's time zone, both ends included (like Reports).
- The summary covers active products only; archived products are off the shelf.
- Stock value uses each product's current cost (the latest-cost rule from receiving), so it is an
  estimate of what the shelf cost to fill, not an accounting valuation such as FIFO.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import InvalidInputError
from app.models import (
    Membership,
    MovementReason,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderReceipt,
    Refund,
    Sale,
    StockMovement,
    User,
)
from app.schemas.inventory import InventorySummary, LedgerEntry, MovementSource, Person

CENT = Decimal("0.01")


@dataclass(frozen=True)
class LedgerFilters:
    reason: MovementReason | None = None
    q: str | None = None  # product name or SKU, partial match
    product_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    start: date | None = None  # store day, included
    end: date | None = None  # store day, included


def _like(text: str) -> str:
    """A LIKE pattern for `text`, with its own wildcards escaped ("50%" means the literal text)."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _bounds(org: Organization, start: date | None, end: date | None):
    """Store days as [local midnight of start, local midnight after end)."""
    if start and end and end < start:
        raise InvalidInputError(
            "The end date is before the start date.", fields={"end": "Before the start"}
        )
    zone = ZoneInfo(org.timezone)
    since = datetime.combine(start, time.min, tzinfo=zone) if start else None
    until = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone) if end else None
    return since, until


def _conditions(org: Organization, filters: LedgerFilters) -> list:
    conditions = [StockMovement.organization_id == org.id]
    if filters.reason:
        conditions.append(StockMovement.reason == filters.reason.value)
    if filters.product_id:
        conditions.append(StockMovement.product_id == filters.product_id)
    if filters.user_id:
        conditions.append(StockMovement.created_by_user_id == filters.user_id)
    if filters.q:
        term = _like(filters.q)
        conditions.append(
            or_(Product.name.ilike(term, escape="\\"), Product.sku.ilike(term, escape="\\"))
        )
    since, until = _bounds(org, filters.start, filters.end)
    if since:
        conditions.append(StockMovement.created_at >= since)
    if until:
        conditions.append(StockMovement.created_at < until)
    return conditions


def _source(row) -> MovementSource | None:
    # Same formats as Sale.receipt_code, Refund.refund_code and PurchaseOrder.code.
    if row.refund_number is not None:
        return MovementSource(
            kind="refund", id=row.refund_sale_id, code=f"R-{row.refund_number:06d}"
        )
    if row.receipt_number is not None:
        return MovementSource(kind="sale", id=row.sale_id, code=f"S-{row.receipt_number:06d}")
    if row.po_number is not None:
        return MovementSource(kind="purchase_order", id=row.po_id, code=f"PO-{row.po_number:06d}")
    return None


def list_ledger(
    db: Session, org: Organization, filters: LedgerFilters, *, limit: int, offset: int
) -> tuple[list[LedgerEntry], int]:
    """Every stock movement in the store that matches `filters`, newest first."""
    conditions = _conditions(org, filters)
    total = (
        db.scalar(
            select(func.count())
            .select_from(StockMovement)
            .join(Product, Product.id == StockMovement.product_id)
            .where(*conditions)
        )
        or 0
    )
    rows = db.execute(
        select(
            StockMovement,
            Product.name.label("product_name"),
            Product.sku,
            Product.unit,
            User.full_name.label("created_by_name"),
            Sale.id.label("sale_id"),
            Sale.receipt_number,
            Refund.sale_id.label("refund_sale_id"),
            Refund.refund_number,
            PurchaseOrder.id.label("po_id"),
            PurchaseOrder.po_number,
        )
        .join(Product, Product.id == StockMovement.product_id)
        .outerjoin(User, User.id == StockMovement.created_by_user_id)
        .outerjoin(Sale, Sale.id == StockMovement.sale_id)
        .outerjoin(Refund, Refund.id == StockMovement.refund_id)
        .outerjoin(
            PurchaseOrderReceipt,
            PurchaseOrderReceipt.id == StockMovement.purchase_order_receipt_id,
        )
        .outerjoin(PurchaseOrder, PurchaseOrder.id == PurchaseOrderReceipt.purchase_order_id)
        .where(*conditions)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    entries = [
        LedgerEntry(
            id=row.StockMovement.id,
            created_at=row.StockMovement.created_at,
            product_id=row.StockMovement.product_id,
            product_name=row.product_name,
            sku=row.sku,
            unit=row.unit,
            quantity_change=row.StockMovement.quantity_change,
            balance_after=row.StockMovement.balance_after,
            reason=MovementReason(row.StockMovement.reason),
            note=row.StockMovement.note,
            created_by_name=row.created_by_name,
            source=_source(row),
        )
        for row in rows
    ]
    return entries, total


def stock_summary(db: Session, org: Organization) -> InventorySummary:
    """Units, value and stock status counts for the store's active products."""
    products, units, value, low, out = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(Product.stock_on_hand), 0),
            func.coalesce(func.sum(Product.stock_on_hand * Product.cost), 0),
            # Same thresholds as the product list's stock status filter.
            func.count(
                case(
                    (
                        (Product.stock_on_hand > 0)
                        & (Product.stock_on_hand <= Product.reorder_level),
                        1,
                    )
                )
            ),
            func.count(case((Product.stock_on_hand == 0, 1))),
        ).where(Product.organization_id == org.id, Product.is_active.is_(True))
    ).one()

    # Only people who have changed stock here: the list feeds the ledger's "who" filter, and a
    # name that matches nothing would be a dead end. Membership keeps it to this store's people.
    has_moved_stock = (
        select(StockMovement.id)
        .where(
            StockMovement.organization_id == org.id,
            StockMovement.created_by_user_id == User.id,
        )
        .exists()
    )
    people = db.execute(
        select(User.id, User.full_name)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == org.id, has_moved_stock)
        .order_by(User.full_name, User.id)
    ).all()

    return InventorySummary(
        products=products,
        units_on_hand=int(units),
        stock_value=Decimal(value).quantize(CENT),
        currency=org.currency,
        low_stock=low,
        out_of_stock=out,
        people=[Person(id=user_id, name=name) for user_id, name in people],
    )

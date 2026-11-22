"""The daily demand table for forecasting, built from a store's real records.

It follows the contract in services/ml (`tindawise_ml/data.py`): one row per active product per
store-local day, zero-filled, with

- `units_sold`: units rung up that day (sum of `sale_lines.quantity` for sales whose time falls
  on that store day). Refunds are not subtracted: a return doesn't mean customers wanted less
  that day, and refunds are counted on their own day elsewhere.
- `stockout`: the shelf reached zero that day, so sales may be below what customers wanted.
  From the ledger: some stock movement that day ended at `balance_after = 0`, or nothing moved
  and the balance carried in from the day before was zero. Days before the product existed are
  marked as stockout days too (it couldn't be bought), so models and scoring skip them.

A shelf that was empty overnight and restocked during the day is not flagged, even if morning
customers missed out. The ledger can't tell when customers came.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by, array_agg, distinct_on
from sqlalchemy.orm import Session

from app.models import Organization, Product, Sale, SaleLine, StockMovement


@dataclass(frozen=True)
class DemandRow:
    day: date
    sku: str
    units_sold: int
    stockout: bool


def store_day_bounds(org: Organization, start: date, end: date) -> tuple[datetime, datetime]:
    """[start 00:00, day after end 00:00) in the store's time zone."""
    zone = ZoneInfo(org.timezone)
    return (
        datetime.combine(start, time.min, tzinfo=zone),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone),
    )


def _units_sold(
    db: Session, org: Organization, since: datetime, until: datetime
) -> dict[tuple[uuid.UUID, date], int]:
    local = (
        select(
            SaleLine.product_id,
            func.date(func.timezone(org.timezone, Sale.created_at)).label("day"),
            SaleLine.quantity,
        )
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(Sale.organization_id == org.id, Sale.created_at >= since, Sale.created_at < until)
        .subquery()
    )
    rows = db.execute(
        select(local.c.product_id, local.c.day, func.sum(local.c.quantity)).group_by(
            local.c.product_id, local.c.day
        )
    )
    return {(product_id, day): int(units) for product_id, day, units in rows}


def _ledger_days(
    db: Session, org: Organization, since: datetime, until: datetime
) -> dict[tuple[uuid.UUID, date], tuple[bool, int]]:
    """Per product and store day with movements: (reached zero, balance after the last one)."""
    local = (
        select(
            StockMovement.product_id,
            func.date(func.timezone(org.timezone, StockMovement.created_at)).label("day"),
            StockMovement.balance_after,
            StockMovement.created_at,
            StockMovement.id,
        )
        .where(
            StockMovement.organization_id == org.id,
            StockMovement.created_at >= since,
            StockMovement.created_at < until,
        )
        .subquery()
    )
    last_balance = array_agg(
        aggregate_order_by(local.c.balance_after, local.c.created_at.desc(), local.c.id.desc())
    )[1]
    rows = db.execute(
        select(
            local.c.product_id,
            local.c.day,
            func.bool_or(local.c.balance_after == 0),
            last_balance,
        ).group_by(local.c.product_id, local.c.day)
    )
    return {(pid, day): (bool(hit_zero), int(closing)) for pid, day, hit_zero, closing in rows}


def _opening_balances(db: Session, org: Organization, before: datetime) -> dict[uuid.UUID, int]:
    """Each product's balance after its last movement before `before` (none: never stocked)."""
    rows = db.execute(
        select(StockMovement.product_id, StockMovement.balance_after)
        .where(StockMovement.organization_id == org.id, StockMovement.created_at < before)
        .ext(distinct_on(StockMovement.product_id))
        .order_by(
            StockMovement.product_id, StockMovement.created_at.desc(), StockMovement.id.desc()
        )
    )
    return dict(rows.all())


def daily_demand(db: Session, org: Organization, start: date, end: date) -> list[DemandRow]:
    """The table for `org`'s active products, store days `start` to `end` (both included),
    ordered by day then SKU."""
    if end < start:
        raise ValueError("end is before start")
    products = list(
        db.scalars(
            select(Product)
            .where(Product.organization_id == org.id, Product.is_active.is_(True))
            .order_by(Product.sku)
        )
    )
    if not products:
        return []

    zone = ZoneInfo(org.timezone)
    since, until = store_day_bounds(org, start, end)
    sold = _units_sold(db, org, since, until)
    ledger = _ledger_days(db, org, since, until)
    balance = _opening_balances(db, org, since)
    days = [start + timedelta(days=n) for n in range((end - start).days + 1)]

    rows: list[DemandRow] = []
    for product in products:
        available_from = product.created_at.astimezone(zone).date()
        carried = balance.get(product.id)  # None: no stock ever recorded, so the shelf is empty
        for day in days:
            if day < available_from:
                rows.append(DemandRow(day, product.sku, 0, True))
                continue
            moved = ledger.get((product.id, day))
            if moved is not None:
                stockout, carried = moved
            else:
                stockout = not carried
            rows.append(DemandRow(day, product.sku, sold.get((product.id, day), 0), stockout))
    rows.sort(key=lambda row: (row.day, row.sku))
    return rows

"""The Overview dashboard, computed from recorded sales and current stock.

Definitions (keep in sync with docs/ARCHITECTURE.md):
- Days are calendar days in the store's time zone (`organizations.timezone`), not UTC.
- Weeks run Sunday to Saturday. Comparisons are against the same weekday one week earlier.
- Sales = sum of sale totals. Transactions = number of sales.
- Gross margin = (sales - cost) / sales, using the cost copied onto each sale at checkout.
  Products saved with cost 0 make the margin look higher than it is.
- "Needs attention" = active product with stock at or below its reorder level (out of stock
  included).
- Reorder suggestion (a rule, not a forecast): order enough to reach
  max(2 x reorder level, units sold in the last 14 days). It is shown only when that is above
  zero, so an item with no reorder level and no recent sales gets no number.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from app.models import Organization, Product, Sale, SaleLine
from app.schemas.overview import (
    Overview,
    OverviewDay,
    ReorderLine,
    ReorderSuggestions,
    SalesFigures,
    StockWatchItem,
)

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")
ZERO = Decimal("0.00")

REORDER_LOOKBACK_DAYS = 14
WATCH_LIMIT = 5
REORDER_LIMIT = 5


@dataclass(frozen=True)
class _DayTotals:
    sales: Decimal = ZERO
    transactions: int = 0
    cost: Decimal = ZERO


def _week_start(day: date) -> date:
    """The Sunday on or before `day`."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _daily_totals(
    db: Session,
    org_id: uuid.UUID,
    zone: str,
    start: datetime,
    end: datetime,
    cashier_id: uuid.UUID | None,
) -> dict[date, _DayTotals]:
    # Postgres converts each sale's timestamp to the store's local date. Grouping happens in an
    # outer query so the time zone is passed once.
    filters = [Sale.organization_id == org_id, Sale.created_at >= start, Sale.created_at < end]
    if cashier_id is not None:
        filters.append(Sale.created_by_user_id == cashier_id)
    local = (
        select(
            func.date(func.timezone(zone, Sale.created_at)).label("day"),
            Sale.total,
            Sale.cost_total,
        )
        .where(*filters)
        .subquery()
    )
    rows = db.execute(
        select(
            local.c.day, func.sum(local.c.total), func.count(), func.sum(local.c.cost_total)
        ).group_by(local.c.day)
    )
    return {day: _DayTotals(sales, count, cost) for day, sales, count, cost in rows}


def _figures(totals: _DayTotals, include_costs: bool) -> SalesFigures:
    margin = None
    if include_costs and totals.sales > 0:
        margin = ((totals.sales - totals.cost) / totals.sales).quantize(RATIO)
    return SalesFigures(
        sales=totals.sales.quantize(CENT),
        transactions=totals.transactions,
        gross_margin=margin,
    )


def _sold_recently(
    db: Session, org_id: uuid.UUID, product_ids: list[uuid.UUID], since: datetime
) -> dict[uuid.UUID, int]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(SaleLine.product_id, func.sum(SaleLine.quantity))
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(
            Sale.organization_id == org_id,
            Sale.created_at >= since,
            SaleLine.product_id.in_(product_ids),
        )
        .group_by(SaleLine.product_id)
    )
    return {product_id: int(quantity) for product_id, quantity in rows}


def suggested_quantity(stock_on_hand: int, reorder_level: int, sold_recently: int) -> int:
    """Units to order so stock reaches max(2 x reorder level, recent sales). Never negative."""
    target = max(2 * reorder_level, sold_recently)
    return max(target - stock_on_hand, 0)


def attention_products(db: Session, org_id: uuid.UUID) -> list[Product]:
    """Active products at or below their reorder level: out of stock first, then the lowest
    share of the reorder level, then by name."""
    return list(
        db.scalars(
            select(Product)
            .where(
                Product.organization_id == org_id,
                Product.is_active.is_(True),
                Product.stock_on_hand <= Product.reorder_level,
            )
            .order_by(
                case((Product.stock_on_hand == 0, 0), else_=1),
                cast(Product.stock_on_hand, Numeric) / func.nullif(Product.reorder_level, 0),
                Product.name,
            )
        )
    )


@dataclass(frozen=True)
class ReorderCandidate:
    product: Product
    sold_recently: int
    quantity: int


def reorder_candidates(
    db: Session, org_id: uuid.UUID, attention: list[Product], now: datetime
) -> list[ReorderCandidate]:
    """The reorder rule applied to `attention` (same order). Shared by the Overview and by
    "create a purchase order from suggestions", so both always agree."""
    since = now - timedelta(days=REORDER_LOOKBACK_DAYS)
    sold = _sold_recently(db, org_id, [p.id for p in attention], since)
    candidates = []
    for product in attention:
        quantity = suggested_quantity(
            product.stock_on_hand, product.reorder_level, sold.get(product.id, 0)
        )
        if quantity > 0:
            candidates.append(ReorderCandidate(product, sold.get(product.id, 0), quantity))
    return candidates


def build_overview(
    db: Session,
    org: Organization,
    *,
    cashier_id: uuid.UUID | None,
    include_costs: bool,
    now: datetime | None = None,
) -> Overview:
    """`cashier_id` limits sales figures to one cashier; stock figures are always store-wide."""
    now = now or datetime.now(ZoneInfo("UTC"))
    zone = ZoneInfo(org.timezone)
    today = now.astimezone(zone).date()
    this_week = _week_start(today)
    last_week = this_week - timedelta(days=7)

    window_start = datetime.combine(last_week, time.min, tzinfo=zone)
    window_end = datetime.combine(this_week + timedelta(days=7), time.min, tzinfo=zone)
    daily = _daily_totals(db, org.id, org.timezone, window_start, window_end, cashier_id)
    empty = _DayTotals()

    week = []
    for offset in range(7):
        day = this_week + timedelta(days=offset)
        week.append(
            OverviewDay(
                date=day,
                sales=daily.get(day, empty).sales.quantize(CENT) if day <= today else None,
                last_week_sales=daily.get(day - timedelta(days=7), empty).sales.quantize(CENT),
            )
        )

    attention = attention_products(db, org.id)
    out_of_stock = sum(1 for p in attention if p.stock_on_hand == 0)

    reorder_lines = [
        ReorderLine(
            product_id=c.product.id,
            name=c.product.name,
            unit=c.product.unit,
            stock_on_hand=c.product.stock_on_hand,
            reorder_level=c.product.reorder_level,
            sold_recently=c.sold_recently,
            suggested_quantity=c.quantity,
            unit_cost=c.product.cost if include_costs else None,
        )
        for c in reorder_candidates(db, org.id, attention, now)
    ]
    shown = reorder_lines[:REORDER_LIMIT]
    # Priced from the shown lines only, so the total matches what is listed.
    estimated_cost = (
        sum(((line.unit_cost or ZERO) * line.suggested_quantity for line in shown), ZERO).quantize(
            CENT
        )
        if include_costs
        else None
    )

    return Overview(
        as_of=now,
        timezone=org.timezone,
        currency=org.currency,
        sales_scope="mine" if cashier_id else "store",
        costs_visible=include_costs,
        today=_figures(daily.get(today, empty), include_costs),
        same_day_last_week=_figures(daily.get(today - timedelta(days=7), empty), include_costs),
        week=week,
        low_stock_count=len(attention) - out_of_stock,
        out_of_stock_count=out_of_stock,
        stock_to_watch=[
            StockWatchItem(
                id=p.id,
                name=p.name,
                category=p.category.name if p.category else None,
                unit=p.unit,
                stock_on_hand=p.stock_on_hand,
                reorder_level=p.reorder_level,
                stock_status=p.stock_status,
            )
            for p in attention[:WATCH_LIMIT]
        ],
        reorder=ReorderSuggestions(
            lines=shown,
            total_count=len(reorder_lines),
            lookback_days=REORDER_LOOKBACK_DAYS,
            estimated_cost=estimated_cost,
        ),
    )

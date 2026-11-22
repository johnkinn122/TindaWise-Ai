"""The Overview dashboard, computed from recorded sales and current stock.

Definitions (keep in sync with docs/ARCHITECTURE.md):
- Days are calendar days in the store's time zone (`organizations.timezone`), not UTC.
- Weeks run Sunday to Saturday. Comparisons are against the same weekday one week earlier.
- Sales = net sales: sale totals minus refunds, each counted on the day it happened (a refund
  today lowers today's sales, even for an older receipt). Transactions = number of sales.
- Gross margin = (net sales - net cost) / net sales. Net cost = cost copied onto each sale at
  checkout, minus the cost of refunded units put back on the shelf (units not restocked stay a
  loss). Products saved with cost 0 make the margin look higher than it is.
- "Needs attention" = active product with stock at or below its reorder level (out of stock
  included).
- Reorder suggestions come from recent in-stock sales and delivery time: see
  `services/reorder.py` for the rule and why it was chosen.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from app.models import Organization, Product, Refund, Sale
from app.schemas.overview import (
    Overview,
    OverviewDay,
    ReorderLine,
    ReorderSuggestions,
    SalesFigures,
    StockWatchItem,
)
from app.services.reorder import COVER_DAYS, WINDOW_DAYS, reorder_candidates

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")
ZERO = Decimal("0.00")

WATCH_LIMIT = 5
REORDER_LIMIT = 5


@dataclass(frozen=True)
class DayTotals:
    """One store-local day. `sales` and `cost` are gross (as rung up); refunds are separate."""

    sales: Decimal = ZERO
    transactions: int = 0
    cost: Decimal = ZERO
    refunds: Decimal = ZERO
    refund_count: int = 0
    restocked_cost: Decimal = ZERO  # cost of refunded units that went back on the shelf

    @property
    def net_sales(self) -> Decimal:
        return self.sales - self.refunds

    @property
    def net_cost(self) -> Decimal:
        return self.cost - self.restocked_cost


def week_start(day: date) -> date:
    """The Sunday on or before `day`."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def daily_totals(
    db: Session,
    org_id: uuid.UUID,
    zone: str,
    start: datetime,
    end: datetime,
    cashier_id: uuid.UUID | None,
) -> dict[date, DayTotals]:
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
    days = {day: DayTotals(sales, count, cost) for day, sales, count, cost in rows}

    # Refunds land on the day they were given, whenever the sale was. For one cashier's figures,
    # refunds of that cashier's sales count (whoever gave the refund).
    refund_filters = [
        Refund.organization_id == org_id,
        Refund.created_at >= start,
        Refund.created_at < end,
    ]
    refunds_query = select(
        func.date(func.timezone(zone, Refund.created_at)).label("day"),
        Refund.total,
        Refund.restocked_cost,
    ).where(*refund_filters)
    if cashier_id is not None:
        refunds_query = refunds_query.join(Sale, Sale.id == Refund.sale_id).where(
            Sale.created_by_user_id == cashier_id
        )
    refunds = refunds_query.subquery()
    for day, total, count, restocked in db.execute(
        select(
            refunds.c.day,
            func.sum(refunds.c.total),
            func.count(),
            func.sum(refunds.c.restocked_cost),
        ).group_by(refunds.c.day)
    ):
        base = days.get(day, DayTotals())
        days[day] = replace(base, refunds=total, refund_count=count, restocked_cost=restocked)
    return days


def _figures(totals: DayTotals, include_costs: bool) -> SalesFigures:
    margin = None
    net = totals.net_sales
    if include_costs and net > 0:
        margin = ((net - totals.net_cost) / net).quantize(RATIO)
    return SalesFigures(
        sales=net.quantize(CENT),
        refunds=totals.refunds.quantize(CENT),
        transactions=totals.transactions,
        gross_margin=margin,
    )


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
    this_week = week_start(today)
    last_week = this_week - timedelta(days=7)

    window_start = datetime.combine(last_week, time.min, tzinfo=zone)
    window_end = datetime.combine(this_week + timedelta(days=7), time.min, tzinfo=zone)
    daily = daily_totals(db, org.id, org.timezone, window_start, window_end, cashier_id)
    empty = DayTotals()

    week = []
    for offset in range(7):
        day = this_week + timedelta(days=offset)
        week.append(
            OverviewDay(
                date=day,
                sales=daily.get(day, empty).net_sales.quantize(CENT) if day <= today else None,
                last_week_sales=daily.get(day - timedelta(days=7), empty).net_sales.quantize(CENT),
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
            on_order=c.on_order,
            reorder_level=c.product.reorder_level,
            suggested_quantity=c.quantity,
            basis=c.basis,
            daily_rate=(
                Decimal(str(c.daily_rate)).quantize(Decimal("0.1"))
                if c.daily_rate is not None
                else None
            ),
            in_stock_days=c.in_stock_days,
            lead_time_days=c.lead_time_days,
            lead_time_source=c.lead_time_source,
            supplier_name=c.supplier_name,
            unit_cost=c.product.cost if include_costs else None,
        )
        for c in reorder_candidates(db, org, now)
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
            window_days=WINDOW_DAYS,
            cover_days=COVER_DAYS,
            estimated_cost=estimated_cost,
        ),
    )

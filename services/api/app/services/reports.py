"""The sales report. Definitions (keep in sync with docs/ARCHITECTURE.md):

- A period is a range of calendar days in the store's time zone, both ends included.
- The comparison period has the same number of days and ends the day before the period starts.
- Sales = sum of sale totals. Gross profit = sales - cost, using the cost copied onto each sale
  line at checkout. Gross margin = gross profit / sales.
- Buckets: by day up to 31 days, by week (Sunday start) up to 182 days, by month beyond that.
- Category is the product's category today (sales don't record it), so moving a product to
  another category moves its past sales with it.
- Purchases = stock received on purchase orders in the period, valued at the order's unit cost.
"""

import uuid
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session

from app.core.errors import InvalidInputError
from app.models import (
    Category,
    MovementReason,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderReceipt,
    Sale,
    SaleLine,
    StockMovement,
    Supplier,
)
from app.schemas.report import (
    CategoryRow,
    Granularity,
    PaymentRow,
    Period,
    Preset,
    ProductRow,
    ProductSort,
    ReportSummary,
    SalesReport,
    SeriesPoint,
    SupplierRow,
)
from app.services.overview import DayTotals, daily_totals, week_start

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")
ZERO = Decimal("0")

MAX_DAYS = 366
TOP_PRODUCTS = 10  # default; exports ask for more


# ── Periods ─────────────────────────────────────────────────────────────────


def _period(start: date, end: date) -> Period:
    return Period(start=start, end=end, days=(end - start).days + 1)


def _month_start(day: date) -> date:
    return day.replace(day=1)


def resolve_period(
    today: date, preset: Preset | None, start: date | None, end: date | None
) -> Period:
    """A custom range wins over a preset; with neither, the last 7 days."""
    if start is not None or end is not None:
        if start is None or end is None:
            raise InvalidInputError(
                "Choose both a start and an end date.",
                fields={"start" if start is None else "end": "Required"},
            )
        if end < start:
            raise InvalidInputError(
                "The end date is before the start date.", fields={"end": "Before the start"}
            )
        if (end - start).days + 1 > MAX_DAYS:
            raise InvalidInputError(
                f"Choose a range of at most {MAX_DAYS} days.", fields={"start": "Range too long"}
            )
        return _period(start, end)

    match preset or "last_7_days":
        case "today":
            return _period(today, today)
        case "yesterday":
            return _period(today - timedelta(days=1), today - timedelta(days=1))
        case "last_7_days":
            return _period(today - timedelta(days=6), today)
        case "last_30_days":
            return _period(today - timedelta(days=29), today)
        case "this_month":
            return _period(_month_start(today), today)
        case "last_month":
            last_day = _month_start(today) - timedelta(days=1)
            return _period(_month_start(last_day), last_day)
    raise AssertionError(preset)  # pragma: no cover - Literal covers every case


def previous_period(period: Period) -> Period:
    end = period.start - timedelta(days=1)
    return _period(end - timedelta(days=period.days - 1), end)


def granularity_for(days: int) -> Granularity:
    if days <= 31:
        return "day"
    if days <= 182:
        return "week"
    return "month"


def _bucket_start(day: date, granularity: Granularity) -> date:
    if granularity == "week":
        return week_start(day)
    if granularity == "month":
        return _month_start(day)
    return day


def _buckets(period: Period, granularity: Granularity) -> Iterator[date]:
    current = _bucket_start(period.start, granularity)
    while current <= period.end:
        yield current
        if granularity == "day":
            current += timedelta(days=1)
        elif granularity == "week":
            current += timedelta(days=7)
        else:
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


# ── Figures ─────────────────────────────────────────────────────────────────


def _bounds(period: Period, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The period as [first local midnight, midnight after the last day)."""
    start = datetime.combine(period.start, time.min, tzinfo=zone)
    end = datetime.combine(period.end + timedelta(days=1), time.min, tzinfo=zone)
    return start, end


def _ratio(part: Decimal, whole: Decimal) -> Decimal | None:
    return (part / whole).quantize(RATIO) if whole > 0 else None


def _summary(days: dict[date, DayTotals], items_sold: int) -> ReportSummary:
    sales = sum((d.sales for d in days.values()), ZERO)
    cost = sum((d.cost for d in days.values()), ZERO)
    transactions = sum(d.transactions for d in days.values())
    return ReportSummary(
        sales=sales.quantize(CENT),
        transactions=transactions,
        average_sale=(sales / transactions).quantize(CENT) if transactions else None,
        gross_profit=(sales - cost).quantize(CENT),
        gross_margin=_ratio(sales - cost, sales),
        items_sold=items_sold,
    )


def _line_filters(org_id: uuid.UUID, start: datetime, end: datetime) -> list:
    return [Sale.organization_id == org_id, Sale.created_at >= start, Sale.created_at < end]


def _items_sold(db: Session, org_id: uuid.UUID, start: datetime, end: datetime) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(SaleLine.quantity), 0))
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(*_line_filters(org_id, start, end))
    )
    return int(total or 0)


_LINE_PROFIT = SaleLine.line_total - SaleLine.unit_cost * SaleLine.quantity


def _products(
    db: Session,
    org_id: uuid.UUID,
    start: datetime,
    end: datetime,
    sort: ProductSort,
    limit: int,
) -> tuple[list[ProductRow], int]:
    quantity = func.sum(SaleLine.quantity).label("quantity")
    sales = func.sum(SaleLine.line_total).label("sales")
    profit = func.sum(_LINE_PROFIT).label("profit")
    order = {"sales": sales, "gross_profit": profit, "quantity": quantity}[sort]
    rows = db.execute(
        select(Product.id, Product.name, Product.sku, Product.unit, quantity, sales, profit)
        .select_from(SaleLine)
        .join(Sale, Sale.id == SaleLine.sale_id)
        .join(Product, Product.id == SaleLine.product_id)
        .where(*_line_filters(org_id, start, end))
        .group_by(Product.id)
        .order_by(order.desc(), Product.name)
        .limit(limit)
    ).all()
    count = db.scalar(
        select(func.count(distinct(SaleLine.product_id)))
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(*_line_filters(org_id, start, end))
    )
    return [
        ProductRow(
            product_id=pid,
            name=name,
            sku=sku,
            unit=unit,
            quantity=int(qty),
            sales=sale_sum.quantize(CENT),
            gross_profit=profit_sum.quantize(CENT),
            gross_margin=_ratio(profit_sum, sale_sum),
        )
        for pid, name, sku, unit, qty, sale_sum, profit_sum in rows
    ], int(count or 0)


def _categories(
    db: Session, org_id: uuid.UUID, start: datetime, end: datetime
) -> list[CategoryRow]:
    sales = func.sum(SaleLine.line_total).label("sales")
    rows = db.execute(
        select(
            Category.id,
            Category.name,
            func.sum(SaleLine.quantity),
            sales,
            func.sum(_LINE_PROFIT),
        )
        .select_from(SaleLine)
        .join(Sale, Sale.id == SaleLine.sale_id)
        .join(Product, Product.id == SaleLine.product_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .where(*_line_filters(org_id, start, end))
        .group_by(Category.id, Category.name)
        .order_by(sales.desc())
    ).all()
    return [
        CategoryRow(
            category_id=cid,
            name=name or "No category",
            quantity=int(qty),
            sales=sale_sum.quantize(CENT),
            gross_profit=profit_sum.quantize(CENT),
        )
        for cid, name, qty, sale_sum, profit_sum in rows
    ]


def _payments(db: Session, org_id: uuid.UUID, start: datetime, end: datetime) -> list[PaymentRow]:
    sales = func.sum(Sale.total).label("sales")
    rows = db.execute(
        select(Sale.payment_method, sales, func.count())
        .where(*_line_filters(org_id, start, end))
        .group_by(Sale.payment_method)
        .order_by(sales.desc())
    ).all()
    return [
        PaymentRow(method=method, sales=total.quantize(CENT), transactions=count)
        for method, total, count in rows
    ]


def _suppliers(db: Session, org_id: uuid.UUID, start: datetime, end: datetime) -> list[SupplierRow]:
    """Stock received on purchase orders in the period, valued at each order line's unit cost."""
    value = func.sum(StockMovement.quantity_change * PurchaseOrderLine.unit_cost).label("value")
    rows = db.execute(
        select(Supplier.id, Supplier.name, value, func.count(distinct(PurchaseOrderReceipt.id)))
        .select_from(StockMovement)
        .join(
            PurchaseOrderReceipt, PurchaseOrderReceipt.id == StockMovement.purchase_order_receipt_id
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderReceipt.purchase_order_id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(
            PurchaseOrderLine,
            and_(
                PurchaseOrderLine.purchase_order_id == PurchaseOrder.id,
                PurchaseOrderLine.product_id == StockMovement.product_id,
            ),
        )
        .where(
            StockMovement.organization_id == org_id,
            StockMovement.reason == MovementReason.PURCHASE.value,
            StockMovement.created_at >= start,
            StockMovement.created_at < end,
        )
        .group_by(Supplier.id, Supplier.name)
        .order_by(value.desc())
    ).all()
    return [
        SupplierRow(supplier_id=sid, name=name, received_value=total.quantize(CENT), deliveries=n)
        for sid, name, total, n in rows
    ]


# ── The report ──────────────────────────────────────────────────────────────


def build_sales_report(
    db: Session,
    org: Organization,
    *,
    preset: Preset | None = None,
    start: date | None = None,
    end: date | None = None,
    product_sort: ProductSort = "sales",
    top: int = TOP_PRODUCTS,
    now: datetime | None = None,
) -> SalesReport:
    zone = ZoneInfo(org.timezone)
    today = (now or datetime.now(zone)).astimezone(zone).date()
    period = resolve_period(today, preset, start, end)
    previous = previous_period(period)
    granularity = granularity_for(period.days)

    cur_start, cur_end = _bounds(period, zone)
    prev_start, prev_end = _bounds(previous, zone)
    current_days = daily_totals(db, org.id, org.timezone, cur_start, cur_end, None)
    previous_days = daily_totals(db, org.id, org.timezone, prev_start, prev_end, None)

    buckets: dict[date, list[DayTotals]] = {b: [] for b in _buckets(period, granularity)}
    for day, totals in current_days.items():
        buckets[_bucket_start(day, granularity)].append(totals)
    series = [
        SeriesPoint(
            start=bucket,
            sales=sum((d.sales for d in days), ZERO).quantize(CENT),
            transactions=sum(d.transactions for d in days),
            gross_profit=sum((d.sales - d.cost for d in days), ZERO).quantize(CENT),
        )
        for bucket, days in buckets.items()
    ]

    products, product_count = _products(db, org.id, cur_start, cur_end, product_sort, top)
    suppliers = _suppliers(db, org.id, cur_start, cur_end)
    return SalesReport(
        timezone=org.timezone,
        currency=org.currency,
        period=period,
        previous_period=previous,
        granularity=granularity,
        summary=_summary(current_days, _items_sold(db, org.id, cur_start, cur_end)),
        previous_summary=_summary(previous_days, _items_sold(db, org.id, prev_start, prev_end)),
        series=series,
        products=products,
        product_count=product_count,
        product_sort=product_sort,
        categories=_categories(db, org.id, cur_start, cur_end),
        payments=_payments(db, org.id, cur_start, cur_end),
        suppliers=suppliers,
        purchases_total=sum((s.received_value for s in suppliers), ZERO).quantize(CENT),
    )

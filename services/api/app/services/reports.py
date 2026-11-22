"""The sales report. Definitions (keep in sync with docs/ARCHITECTURE.md):

- A period is a range of calendar days in the store's time zone, both ends included.
- The comparison period has the same number of days and ends the day before the period starts.
- Gross sales = sum of sale totals. Refunds = sum of refunds given in the period, whenever the
  sale was (closed periods never change). Sales (net) = gross sales - refunds.
- Net cost = cost copied onto each sale line at checkout, minus the cost of refunded units put
  back on the shelf. Refunded units not restocked (damaged, spoiled) stay a loss.
- Gross profit = net sales - net cost. Gross margin = gross profit / net sales.
- Transactions = number of sales. Average sale = gross sales / transactions (the basket at
  checkout). Items sold, products, categories and payment methods are net of refunds too, so a
  product can show a negative line in a period with more refunds than sales.
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

from sqlalchemy import Numeric, and_, case, distinct, func, literal, select, union_all
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
    Refund,
    RefundLine,
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
    gross = sum((d.sales for d in days.values()), ZERO)
    refunds = sum((d.refunds for d in days.values()), ZERO)
    net = gross - refunds
    net_cost = sum((d.net_cost for d in days.values()), ZERO)
    transactions = sum(d.transactions for d in days.values())
    return ReportSummary(
        gross_sales=gross.quantize(CENT),
        refunds=refunds.quantize(CENT),
        refund_count=sum(d.refund_count for d in days.values()),
        sales=net.quantize(CENT),
        transactions=transactions,
        average_sale=(gross / transactions).quantize(CENT) if transactions else None,
        gross_profit=(net - net_cost).quantize(CENT),
        gross_margin=_ratio(net - net_cost, net),
        items_sold=items_sold,
    )


def _sale_filters(org_id: uuid.UUID, start: datetime, end: datetime) -> list:
    return [Sale.organization_id == org_id, Sale.created_at >= start, Sale.created_at < end]


def _refund_filters(org_id: uuid.UUID, start: datetime, end: datetime) -> list:
    return [Refund.organization_id == org_id, Refund.created_at >= start, Refund.created_at < end]


def _line_events(org_id: uuid.UUID, start: datetime, end: datetime):
    """Sold lines (+) and refunded lines (-) in the period, as one table with columns
    product_id, quantity, amount, cost. Summing it gives net figures per product."""
    sold = (
        select(
            SaleLine.product_id.label("product_id"),
            SaleLine.quantity.label("quantity"),
            SaleLine.line_total.label("amount"),
            (SaleLine.unit_cost * SaleLine.quantity).label("cost"),
        )
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(*_sale_filters(org_id, start, end))
    )
    refunded = (
        select(
            RefundLine.product_id,
            -RefundLine.quantity,
            -RefundLine.line_total,
            # Restocked units give their cost back; units not restocked stay a loss.
            case(
                (RefundLine.restocked, -(RefundLine.unit_cost * RefundLine.quantity)),
                else_=literal(0, Numeric(12, 2)),
            ),
        )
        .join(Refund, Refund.id == RefundLine.refund_id)
        .where(*_refund_filters(org_id, start, end))
    )
    return union_all(sold, refunded).subquery("line_events")


def _items_sold(db: Session, org_id: uuid.UUID, start: datetime, end: datetime) -> int:
    events = _line_events(org_id, start, end)
    total = db.scalar(select(func.coalesce(func.sum(events.c.quantity), 0)))
    return int(total or 0)


def _products(
    db: Session,
    org_id: uuid.UUID,
    start: datetime,
    end: datetime,
    sort: ProductSort,
    limit: int,
) -> tuple[list[ProductRow], int]:
    events = _line_events(org_id, start, end)
    quantity = func.sum(events.c.quantity).label("quantity")
    sales = func.sum(events.c.amount).label("sales")
    profit = func.sum(events.c.amount - events.c.cost).label("profit")
    order = {"sales": sales, "gross_profit": profit, "quantity": quantity}[sort]
    rows = db.execute(
        select(Product.id, Product.name, Product.sku, Product.unit, quantity, sales, profit)
        .select_from(events)
        .join(Product, Product.id == events.c.product_id)
        .group_by(Product.id)
        .order_by(order.desc(), Product.name)
        .limit(limit)
    ).all()
    count = db.scalar(select(func.count(distinct(events.c.product_id))))
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
    events = _line_events(org_id, start, end)
    sales = func.sum(events.c.amount).label("sales")
    rows = db.execute(
        select(
            Category.id,
            Category.name,
            func.sum(events.c.quantity),
            sales,
            func.sum(events.c.amount - events.c.cost),
        )
        .select_from(events)
        .join(Product, Product.id == events.c.product_id)
        .outerjoin(Category, Category.id == Product.category_id)
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
    """Net sales per payment method. Refunds go back the way the sale was paid."""
    zero = literal(0, Numeric(12, 2))
    events = union_all(
        select(
            Sale.payment_method.label("method"),
            Sale.total.label("gross"),
            zero.label("refunds"),
            literal(1).label("sales_count"),
        ).where(*_sale_filters(org_id, start, end)),
        select(Refund.payment_method, zero, Refund.total, literal(0)).where(
            *_refund_filters(org_id, start, end)
        ),
    ).subquery("payment_events")
    net = func.sum(events.c.gross - events.c.refunds).label("net")
    rows = db.execute(
        select(events.c.method, net, func.sum(events.c.refunds), func.sum(events.c.sales_count))
        .group_by(events.c.method)
        .order_by(net.desc())
    ).all()
    return [
        PaymentRow(
            method=method,
            sales=total.quantize(CENT),
            refunds=refunds.quantize(CENT),
            transactions=int(count),
        )
        for method, total, refunds, count in rows
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
            sales=sum((d.net_sales for d in days), ZERO).quantize(CENT),
            refunds=sum((d.refunds for d in days), ZERO).quantize(CENT),
            transactions=sum(d.transactions for d in days),
            gross_profit=sum((d.net_sales - d.net_cost for d in days), ZERO).quantize(CENT),
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

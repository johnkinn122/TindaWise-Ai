"""Opt-in: create a separate SAMPLE store whose two years of sales come from synthetic history.

    # 1. From services/ml: make the history, ending yesterday (Manila time)
    python -m tindawise_ml generate --end 2026-11-21 --out ../api/sample_history.csv
    # 2. From services/api: write it into a new sample store
    python -m scripts.seed_sample_history --csv sample_history.csv

Not real sales. It exists so the forecasting code can be checked on data that went through the
database (sales -> ledger -> export) and so the Overview and Reports have history to show. Sign in
as `sample-owner@example.com` (password `tindawise-demo`) to see it.

It creates its own store instead of filling the demo store: the demo products' ledgers already
start with their opening stock, and history written before that would break the chain of
`balance_after` values. Also, Playwright runs against the demo store locally.

Rows are bulk-inserted rather than going through checkout one by one (about 20,000 receipts).
They follow the same rules: price and cost snapshots on each line, line total = price x quantity,
one sale movement per line with its running balance, sequential receipt numbers. Prices and costs
stay at today's catalogue values for the whole history.

Refuses to run in production (unless DEMO_MODE is on: the public demo), or if the sample store
already exists.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import uuid
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Category,
    Membership,
    MovementReason,
    Organization,
    Product,
    Role,
    Sale,
    SaleLine,
    StockMovement,
    User,
)
from scripts.seed import DEMO_PASSWORD, PRODUCTS

SAMPLE_ORG_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
SAMPLE_ORG_NAME = "Sample history store (synthetic)"
SAMPLE_OWNER_EMAIL = "sample-owner@example.com"
CENT = Decimal("0.01")
CHUNK = 5_000
OPENING_TIME = time(6, 0)
DELIVERY_TIME = time(7, 0)
FIRST_SALE, LAST_SALE = time(8, 0), time(20, 0)


@dataclass(frozen=True)
class CatalogItem:
    name: str
    sku: str
    barcode: str | None
    category: str
    unit: str
    price: Decimal
    cost: Decimal
    reorder_level: int


DEMO_CATALOG = {
    sku: CatalogItem(name, sku, barcode, category, unit, Decimal(price), Decimal(cost), reorder)
    for name, sku, barcode, category, unit, price, cost, reorder, _ in PRODUCTS
}


@dataclass(frozen=True)
class HistoryDay:
    day: date
    sold: int
    received: int
    closing: int


class HistoryError(ValueError):
    """The CSV can't be written as a consistent ledger."""


def read_history(path: str) -> dict[str, list[HistoryDay]]:
    """Per SKU, the days in order. Needs the columns `tindawise_ml generate` writes."""
    needed = {"date", "sku", "units_sold", "received", "closing_stock"}
    by_sku: dict[str, list[HistoryDay]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = needed - set(reader.fieldnames or [])
        if missing:
            raise HistoryError(f"missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            by_sku[row["sku"]].append(
                HistoryDay(
                    date.fromisoformat(row["date"]),
                    int(row["units_sold"]),
                    int(row["received"]),
                    int(row["closing_stock"]),
                )
            )
    for days in by_sku.values():
        days.sort(key=lambda d: d.day)
    return dict(by_sku)


def check_history(history: dict[str, list[HistoryDay]], today: date) -> tuple[date, date]:
    """The shared first and last day, after checking the history replays without going below
    zero and doesn't reach into today or the future."""
    if not history:
        raise HistoryError("no rows")
    spans = {(days[0].day, days[-1].day, len(days)) for days in history.values()}
    if len(spans) != 1:
        raise HistoryError("every product must cover the same days")
    first, last, count = spans.pop()
    if (last - first).days + 1 != count:
        raise HistoryError("days must be consecutive, with no gaps or repeats")
    if last >= today:
        raise HistoryError(f"the history must end before today ({today}); it ends {last}")
    for sku, days in history.items():
        balance = days[0].closing + days[0].sold - days[0].received  # opening stock
        if balance < 0:
            raise HistoryError(f"{sku}: negative opening stock")
        for d in days:
            if min(d.sold, d.received, d.closing) < 0:
                raise HistoryError(f"{sku} {d.day}: negative units")
            balance += d.received - d.sold
            if balance != d.closing:
                raise HistoryError(f"{sku} {d.day}: closing stock doesn't add up")
    return first, last


def _at(day: date, clock: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, clock, tzinfo=zone)


def _bulk(db: Session, model: type, rows: list[dict]) -> None:
    for i in range(0, len(rows), CHUNK):
        db.execute(insert(model), rows[i : i + CHUNK])


def write_sample_history(
    db: Session,
    org: Organization,
    owner_id: uuid.UUID,
    history: dict[str, list[HistoryDay]],
    catalog: dict[str, CatalogItem],
    *,
    seed: int = 0,
) -> dict[str, int]:
    """Create the catalogue's products in `org` and write `history` as deliveries, receipts and
    their ledger rows. Does not commit. Returns counts of what was written."""
    unknown = sorted(set(history) - set(catalog))
    if unknown:
        raise HistoryError(f"SKUs not in the catalogue: {', '.join(unknown)}")
    zone = ZoneInfo(org.timezone)
    first, _ = check_history(history, datetime.now(zone).date())
    created = _at(first, OPENING_TIME, zone)

    categories = {}
    for name in sorted({catalog[sku].category for sku in history}):
        categories[name] = Category(organization_id=org.id, name=name)
        db.add(categories[name])
    db.flush()

    products: dict[str, Product] = {}
    movements: list[dict] = []
    balance: dict[str, int] = {}
    for sku, days in sorted(history.items()):
        item = catalog[sku]
        product = Product(
            organization_id=org.id,
            category_id=categories[item.category].id,
            name=item.name,
            sku=sku,
            barcode=item.barcode,
            unit=item.unit,
            price=item.price,
            cost=item.cost,
            currency=org.currency,
            stock_on_hand=days[-1].closing,
            reorder_level=item.reorder_level,
            created_at=created,
            updated_at=created,
        )
        db.add(product)
        products[sku] = product
        balance[sku] = days[0].closing + days[0].sold - days[0].received
    db.flush()

    def move(sku: str, change: int, reason: MovementReason, when: datetime, **extra) -> None:
        balance[sku] += change
        movements.append(
            {
                "id": uuid.uuid4(),
                "organization_id": org.id,
                "product_id": products[sku].id,
                "quantity_change": change,
                "balance_after": balance[sku],
                "reason": reason.value,
                "created_by_user_id": owner_id,
                "created_at": when,
                **extra,
            }
        )

    for sku in sorted(history):
        opening = balance[sku]
        if opening:
            balance[sku] = 0
            move(sku, opening, MovementReason.INITIAL, created, note="Opening stock (sample)")

    sales: list[dict] = []
    lines: list[dict] = []
    receipt = 0
    by_day: dict[date, dict[str, HistoryDay]] = defaultdict(dict)
    for sku, days in history.items():
        for d in days:
            by_day[d.day][sku] = d

    for day in sorted(by_day):
        today = by_day[day]
        for sku in sorted(today):
            if today[sku].received:
                when = _at(day, DELIVERY_TIME, zone)
                move(
                    sku, today[sku].received, MovementReason.PURCHASE, when, note="Sample delivery"
                )

        # Every unit sold that day, shuffled into baskets of 1-4 units (repeatable per day).
        rng = random.Random(seed * 1_000_003 + day.toordinal())
        units = [sku for sku in sorted(today) for _ in range(today[sku].sold)]
        rng.shuffle(units)
        baskets: list[list[str]] = []
        while units:
            size = rng.randint(1, 4)
            baskets.append(units[:size])
            units = units[size:]

        open_seconds = (
            datetime.combine(day, LAST_SALE) - datetime.combine(day, FIRST_SALE)
        ).seconds
        for n, basket in enumerate(baskets):
            when = _at(day, FIRST_SALE, zone) + timedelta(
                seconds=open_seconds * n // max(len(baskets), 1)
            )
            quantities: OrderedDict[str, int] = OrderedDict()
            for sku in basket:
                quantities[sku] = quantities.get(sku, 0) + 1
            receipt += 1
            sale_id = uuid.uuid4()
            total = sum((catalog[s].price * q for s, q in quantities.items()), Decimal(0))
            cost = sum((catalog[s].cost * q for s, q in quantities.items()), Decimal(0))
            if rng.random() < 0.25:
                payment = {
                    "payment_method": "e_wallet",
                    "amount_tendered": None,
                    "change_due": None,
                    "payment_reference": f"SAMPLE-{receipt:06d}",
                }
            else:  # cash, rounded up to the next 20 pesos
                tendered = Decimal(math.ceil(total / 20) * 20)
                payment = {
                    "payment_method": "cash",
                    "amount_tendered": tendered,
                    "change_due": (tendered - total).quantize(CENT),
                    "payment_reference": None,
                }
            sales.append(
                {
                    "id": sale_id,
                    "organization_id": org.id,
                    "receipt_number": receipt,
                    "total": total.quantize(CENT),
                    "cost_total": cost.quantize(CENT),
                    "currency": org.currency,
                    "created_by_user_id": owner_id,
                    "created_at": when,
                    **payment,
                }
            )
            for position, (sku, qty) in enumerate(quantities.items(), start=1):
                item = catalog[sku]
                lines.append(
                    {
                        "id": uuid.uuid4(),
                        "sale_id": sale_id,
                        "position": position,
                        "product_id": products[sku].id,
                        "product_name": item.name,
                        "sku": sku,
                        "unit": item.unit,
                        "unit_price": item.price,
                        "unit_cost": item.cost,
                        "quantity": qty,
                        "line_total": (item.price * qty).quantize(CENT),
                    }
                )
                move(
                    sku, -qty, MovementReason.SALE, when,
                    note=f"Receipt S-{receipt:06d}", sale_id=sale_id,
                )  # fmt: skip

    _bulk(db, Sale, sales)
    _bulk(db, SaleLine, lines)
    _bulk(db, StockMovement, movements)
    org.last_receipt_number = receipt
    for sku, product in products.items():
        assert balance[sku] == product.stock_on_hand, f"{sku}: ledger and stock disagree"
    return {"products": len(products), "sales": len(sales), "lines": len(lines),
            "movements": len(movements)}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.seed_sample_history")
    parser.add_argument("--csv", required=True, help="output of `tindawise_ml generate`")
    parser.add_argument("--seed", type=int, default=0, help="how units are grouped into receipts")
    args = parser.parse_args(argv)

    if not get_settings().sample_data_allowed:
        print("Refusing to write sample data in production (DEMO_MODE is off).", file=sys.stderr)
        return 1
    try:
        history = read_history(args.csv)
    except (OSError, HistoryError, ValueError) as error:
        print(f"Can't use {args.csv}: {error}", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        if db.get(Organization, SAMPLE_ORG_ID):
            print(f"The sample store already exists ({SAMPLE_ORG_ID}). Nothing written.")
            return 0
        org = Organization(id=SAMPLE_ORG_ID, name=SAMPLE_ORG_NAME, currency="PHP")
        owner = User(
            email=SAMPLE_OWNER_EMAIL,
            full_name="Sample Owner",
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add_all([org, owner])
        db.flush()
        db.add(Membership(user_id=owner.id, organization_id=org.id, role=Role.OWNER.value))
        try:
            counts = write_sample_history(db, org, owner.id, history, DEMO_CATALOG, seed=args.seed)
        except HistoryError as error:
            db.rollback()
            print(f"Can't use {args.csv}: {error}", file=sys.stderr)
            return 1
        db.commit()

    print(
        f"Created {SAMPLE_ORG_NAME} ({SAMPLE_ORG_ID}): {counts['products']} products, "
        f"{counts['sales']:,} receipts, {counts['lines']:,} lines, "
        f"{counts['movements']:,} stock movements."
    )
    print(f"Sign in as {SAMPLE_OWNER_EMAIL} (password {DEMO_PASSWORD}). Local use only.")
    print(f"Export: python -m scripts.export_demand --org {SAMPLE_ORG_ID} --out demand.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())

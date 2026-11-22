"""The opt-in sample-history seeder and the demand export (scripts/)."""

import csv
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Organization, Product, Role, Sale, SaleLine, StockMovement
from app.services.demand_history import daily_demand
from scripts import export_demand
from scripts.seed_sample_history import (
    DEMO_CATALOG,
    CatalogItem,
    HistoryDay,
    HistoryError,
    check_history,
    write_sample_history,
)
from tests.conftest import make_member

CATALOG = {
    "A-1": CatalogItem("Item A", "A-1", None, "Snacks", "pcs", Decimal("12.50"), Decimal("10"), 3),
    "B-1": CatalogItem("Item B", "B-1", None, "Drinks", "btl", Decimal("55.00"), Decimal("46"), 2),
}
START = date(2025, 3, 3)


def days(rows: list[tuple[int, int, int]], start: date = START) -> list[HistoryDay]:
    """(sold, received, closing) per day from `start`."""
    return [HistoryDay(start + timedelta(n), s, r, c) for n, (s, r, c) in enumerate(rows)]


# A: opens with 5, sells out on day 2, nothing on day 3, delivery of 6 on day 4.
# B: opens with 2, a delivery and sales every day, never runs out.
HISTORY = {
    "A-1": days([(3, 0, 2), (2, 0, 0), (0, 0, 0), (4, 6, 2), (1, 0, 1)]),
    "B-1": days([(1, 0, 1), (2, 3, 2), (1, 0, 1), (0, 2, 3), (3, 1, 1)]),
}


@pytest.fixture
def seeded(org) -> Organization:
    owner = make_member(org, Role.OWNER)
    with SessionLocal() as db:
        store = db.get(Organization, org.id)
        write_sample_history(db, store, owner.id, HISTORY, CATALOG, seed=1)
        db.commit()
    return org


def test_the_database_gives_back_the_same_table(seeded):
    """synthetic history -> sales and ledger -> daily_demand: the same units and stockouts."""
    with SessionLocal() as db:
        rows = daily_demand(db, db.get(Organization, seeded.id), START, START + timedelta(4))
    for sku, history in HISTORY.items():
        mine = [r for r in rows if r.sku == sku]
        assert [r.units_sold for r in mine] == [d.sold for d in history]
        assert [r.stockout for r in mine] == [d.closing == 0 for d in history]


def test_ledger_balances_chain_and_match_stock_on_hand(seeded):
    with SessionLocal() as db:
        for product in db.scalars(select(Product).where(Product.organization_id == seeded.id)):
            moves = db.scalars(
                select(StockMovement)
                .where(StockMovement.product_id == product.id)
                .order_by(StockMovement.created_at, StockMovement.id)
            ).all()
            running = 0
            for move in moves:
                running += move.quantity_change
                assert move.balance_after == running
            assert running == product.stock_on_hand == HISTORY[product.sku][-1].closing
            assert moves[0].reason == "initial"


def test_receipts_are_consistent_and_numbered(seeded):
    with SessionLocal() as db:
        sales = db.scalars(
            select(Sale).where(Sale.organization_id == seeded.id).order_by(Sale.receipt_number)
        ).all()
        assert [s.receipt_number for s in sales] == list(range(1, len(sales) + 1))
        assert db.get(Organization, seeded.id).last_receipt_number == len(sales)
        for sale in sales:
            assert sale.total == sum(line.line_total for line in sale.lines)
            assert sale.cost_total == sum(line.unit_cost * line.quantity for line in sale.lines)
            assert len({line.product_id for line in sale.lines}) == len(sale.lines)  # merged
            if sale.payment_method == "cash":
                assert sale.amount_tendered >= sale.total
        units = db.scalar(
            select(func.sum(SaleLine.quantity)).join(Sale).where(Sale.organization_id == seeded.id)
        )
        assert units == sum(d.sold for h in HISTORY.values() for d in h)
        # Every sale movement points at its receipt.
        sale_moves = db.scalar(
            select(func.count()).where(
                StockMovement.organization_id == seeded.id, StockMovement.reason == "sale"
            )
        )
        lines = db.scalar(
            select(func.count(SaleLine.id)).join(Sale).where(Sale.organization_id == seeded.id)
        )
        assert sale_moves == lines


def test_same_seed_same_receipts(org, other_org):
    def receipts(store_org) -> list[tuple]:
        owner = make_member(store_org, Role.OWNER)
        with SessionLocal() as db:
            store = db.get(Organization, store_org.id)
            write_sample_history(db, store, owner.id, HISTORY, CATALOG, seed=7)
            db.commit()
            return [
                (s.total, s.payment_method, s.created_at)
                for s in db.scalars(
                    select(Sale)
                    .where(Sale.organization_id == store_org.id)
                    .order_by(Sale.receipt_number)
                )
            ]

    assert receipts(org) == receipts(other_org)


@pytest.mark.parametrize(
    ("history", "message"),
    [
        ({}, "no rows"),
        ({"A-1": HISTORY["A-1"], "B-1": HISTORY["B-1"][:-1]}, "same days"),
        ({"A-1": [HISTORY["A-1"][0], HISTORY["A-1"][2]]}, "consecutive"),
        ({"A-1": days([(1, 0, 5), (1, 0, 3)])}, "doesn't add up"),
        ({"A-1": days([(5, 0, 0)], start=date(2026, 11, 22))}, "before today"),
        ({"A-1": days([(3, 0, 1)])}, None),  # fine: opening stock 4
        ({"A-1": days([(1, 0, 0), (0, 0, -1)])}, "negative"),
    ],
)
def test_history_checks(history, message):
    today = date(2026, 11, 22)
    if message is None:
        check_history(history, today)
        return
    with pytest.raises(HistoryError, match=message):
        check_history(history, today)


def test_unknown_skus_are_refused(org):
    owner = make_member(org, Role.OWNER)
    with SessionLocal() as db, pytest.raises(HistoryError, match="not in the catalogue"):
        write_sample_history(db, db.get(Organization, org.id), owner.id, HISTORY, DEMO_CATALOG)


def test_demo_catalog_matches_the_seeded_products():
    assert len(DEMO_CATALOG) == 17
    assert DEMO_CATALOG["NDL-001"].price == Decimal("16.00")


def test_export_writes_the_contract_csv(seeded, tmp_path, capsys):
    out = tmp_path / "demand.csv"
    end = START + timedelta(4)
    code = export_demand.main(
        ["--org", str(seeded.id), "--start", str(START), "--end", str(end), "--out", str(out)]
    )
    assert code == 0
    with open(out, newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == ["date", "sku", "units_sold", "stockout"]
    assert len(rows) == 10
    assert rows[0] == {"date": "2025-03-03", "sku": "A-1", "units_sold": "3", "stockout": "False"}
    assert rows[2] == {"date": "2025-03-04", "sku": "A-1", "units_sold": "2", "stockout": "True"}
    assert "Wrote 10 rows" in capsys.readouterr().out


def test_export_defaults_to_first_product_day_through_yesterday(seeded, tmp_path):
    out = tmp_path / "demand.csv"
    assert export_demand.main(["--org", str(seeded.id), "--out", str(out)]) == 0
    with open(out, newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["date"] == "2025-03-03"
    assert date.fromisoformat(rows[-1]["date"]) < date.today() + timedelta(days=1)


def test_export_refuses_unknown_store_and_bad_range(seeded, tmp_path, capsys):
    out = str(tmp_path / "x.csv")
    unknown = "00000000-0000-4000-8000-00000000dead"
    assert export_demand.main(["--org", unknown, "--out", out]) == 1
    bad = ["--org", str(seeded.id), "--start", "2025-03-05", "--end", "2025-03-01", "--out", out]
    assert export_demand.main(bad) == 1
    assert "before the start" in capsys.readouterr().err

"""The daily demand table built from real records (app/services/demand_history.py)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update

from app.db.session import SessionLocal
from app.models import Organization, Product, StockMovement
from app.services.demand_history import DemandRow, daily_demand
from tests.test_refunds import refund
from tests.test_reports import sell

NOV_1 = date(2026, 11, 1)


def manila(day: date, hour: int, minute: int = 0) -> datetime:
    """A Manila wall-clock time as UTC (Manila is UTC+8, no daylight saving)."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC) - timedelta(hours=8)


def backdate_product(product: dict, when: datetime) -> None:
    """Move a product's creation and its opening-stock movement to `when`."""
    with SessionLocal() as db:
        db.execute(update(Product).where(Product.id == product["id"]).values(created_at=when))
        db.execute(
            update(StockMovement)
            .where(StockMovement.product_id == product["id"], StockMovement.reason == "initial")
            .values(created_at=when)
        )
        db.commit()


def sell_at(client, headers, lines, when: datetime) -> dict:
    """Ring up a sale through the API, then move it and its stock movements to `when`."""
    sale = sell(client, headers, lines, when=when)
    with SessionLocal() as db:
        db.execute(
            update(StockMovement).where(StockMovement.sale_id == sale["id"]).values(created_at=when)
        )
        db.commit()
    return sale


def adjust_at(client, headers, product, change: int, when: datetime) -> None:
    response = client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"quantity_change": change, "reason": "purchase" if change > 0 else "damage"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        db.execute(
            update(StockMovement)
            .where(StockMovement.id == response.json()["id"])
            .values(created_at=when)
        )
        db.commit()


def table(org, start=NOV_1, end=date(2026, 11, 5)) -> list[DemandRow]:
    with SessionLocal() as db:
        return daily_demand(db, db.get(Organization, org.id), start, end)


def column(rows: list[DemandRow], sku: str, field: str) -> list:
    return [getattr(r, field) for r in rows if r.sku == sku]


@pytest.fixture
def stocked(make_product):
    """Make a product with opening stock that has existed since 1 Nov, 08:00 Manila."""

    def _make(**overrides) -> dict:
        product = make_product(**overrides)
        backdate_product(product, manila(NOV_1, 8))
        return product

    return _make


def test_zero_filled_one_row_per_product_per_day_ordered(org, stocked):
    stocked(sku="B-1")
    stocked(sku="A-1")
    rows = table(org)
    assert len(rows) == 5 * 2
    assert [(r.day, r.sku) for r in rows[:4]] == [
        (NOV_1, "A-1"),
        (NOV_1, "B-1"),
        (date(2026, 11, 2), "A-1"),
        (date(2026, 11, 2), "B-1"),
    ]
    assert all(r.units_sold == 0 and not r.stockout for r in rows)


def test_units_sold_fall_on_the_store_day(client, headers, org, stocked):
    product = stocked(sku="A-1", initial_stock=50)
    sell_at(client, headers, [(product, 2)], manila(date(2026, 11, 2), 23, 30))
    sell_at(client, headers, [(product, 3)], manila(date(2026, 11, 3), 0, 30))  # 16:30 UTC Nov 2
    sell_at(client, headers, [(product, 1)], manila(date(2026, 11, 3), 9))
    assert column(table(org), "A-1", "units_sold") == [0, 2, 4, 0, 0]


def test_stockout_from_the_ledger_until_restocked(client, headers, org, stocked):
    product = stocked(sku="A-1", initial_stock=3)
    sell_at(client, headers, [(product, 3)], manila(date(2026, 11, 2), 15))  # shelf empty
    adjust_at(client, headers, product, 10, manila(date(2026, 11, 4), 7))  # delivery
    assert column(table(org), "A-1", "stockout") == [False, True, True, False, False]
    # Nov 3: nothing moved, but the balance carried in was zero.


def test_restocked_later_the_same_day_carries_the_new_balance(client, headers, org, stocked):
    product = stocked(sku="A-1", initial_stock=3)
    nov_2 = date(2026, 11, 2)
    sell_at(client, headers, [(product, 3)], manila(nov_2, 10))  # empty at 10:00
    adjust_at(client, headers, product, 10, manila(nov_2, 15))  # restocked at 15:00
    # Nov 2 reached zero; Nov 3 onwards start from the day's *last* balance (10), not its first.
    assert column(table(org), "A-1", "stockout") == [False, True, False, False, False]


def test_a_shelf_emptied_by_damage_is_a_stockout(client, headers, org, stocked):
    product = stocked(sku="A-1", initial_stock=2)
    adjust_at(client, headers, product, -2, manila(date(2026, 11, 3), 12))
    assert column(table(org), "A-1", "stockout") == [False, False, True, True, True]


def test_balance_before_the_range_carries_in(client, headers, org, stocked):
    product = stocked(sku="A-1", initial_stock=3)
    sell_at(client, headers, [(product, 3)], manila(NOV_1, 15))
    rows = table(org, start=date(2026, 11, 3))
    assert column(rows, "A-1", "stockout") == [True, True, True]  # still empty from Nov 1


def test_days_before_a_product_existed_are_stockouts(org, make_product):
    product = make_product(sku="A-1")
    backdate_product(product, manila(date(2026, 11, 3), 10))
    rows = table(org)
    assert column(rows, "A-1", "stockout") == [True, True, False, False, False]
    assert column(rows, "A-1", "units_sold") == [0] * 5


def test_a_product_never_stocked_is_out_every_day(org, stocked):
    stocked(sku="A-1", initial_stock=0)
    assert column(table(org), "A-1", "stockout") == [True] * 5


def test_refunds_do_not_reduce_units_sold(client, headers, org, stocked):
    product = stocked(sku="A-1", initial_stock=10)
    sale = sell_at(client, headers, [(product, 2)], manila(date(2026, 11, 2), 10))
    assert refund(client, headers, sale, [(0, 1)]).status_code == 201
    assert column(table(org), "A-1", "units_sold") == [0, 2, 0, 0, 0]


def test_archived_products_are_left_out(client, headers, org, stocked):
    stocked(sku="A-1")
    archived = stocked(sku="B-1")
    assert client.delete(f"/api/v1/products/{archived['id']}", headers=headers).status_code == 204
    assert {r.sku for r in table(org)} == {"A-1"}


def test_other_stores_records_never_count(client, headers, other_headers, org, other_org, stocked):
    stocked(sku="A-1", initial_stock=10)
    theirs = client.post(
        "/api/v1/products",
        json={"name": "Theirs", "sku": "A-1", "price": "10.00", "initial_stock": 10},
        headers=other_headers,
    ).json()
    backdate_product(theirs, manila(NOV_1, 8))
    sell_at(client, other_headers, [(theirs, 10)], manila(date(2026, 11, 2), 10))
    rows = table(org)
    assert column(rows, "A-1", "units_sold") == [0] * 5
    assert column(rows, "A-1", "stockout") == [False] * 5
    assert column(table(other_org), "A-1", "units_sold") == [0, 10, 0, 0, 0]


def test_no_products_gives_an_empty_table(org):
    assert table(org) == []


def test_end_before_start_is_refused(org):
    with pytest.raises(ValueError, match="before start"):
        table(org, start=date(2026, 11, 5), end=NOV_1)

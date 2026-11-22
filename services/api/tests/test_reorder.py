"""Reorder suggestions from recent in-stock sales and delivery time (app/services/reorder.py)."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update

from app.db.session import SessionLocal
from app.models import Organization, PurchaseOrder
from app.services.reorder import ReorderCandidate, _on_order, reorder_candidates, suggest
from tests.test_demand_history import adjust_at, backdate_product, manila, sell_at
from tests.test_purchase_orders import URL as PO_URL
from tests.test_purchase_orders import draft, receive

NOV_1 = date(2026, 11, 1)
# Monday 30 Nov 2026, 10:00 Manila. The window is the 28 complete days 2 to 29 Nov.
NOW = datetime(2026, 11, 30, 2, 0, tzinfo=UTC)
WINDOW = [date(2026, 11, 2) + timedelta(days=n) for n in range(28)]


# ── The rule ────────────────────────────────────────────────────────────────


def rule(**overrides):
    args = {"stock_on_hand": 0, "on_order": 0, "reorder_level": 5, "in_stock_units": [2] * 28,
            "lead_time_days": 3} | overrides  # fmt: skip
    return suggest(**args)


def test_steady_seller_orders_lead_time_plus_cover():
    # 2 a day, no spread: reorder point 2 x 3 = 6; order 2 x (3 + 10) - position.
    assert rule(stock_on_hand=6) == (20, "recent_sales", 2.0)
    assert rule(stock_on_hand=7) == (0, "recent_sales", 2.0)
    assert rule(stock_on_hand=0) == (26, "recent_sales", 2.0)


def test_buffer_grows_with_spread_and_lead_time():
    # Alternating 1 and 3: mean 2, spread 1. Lead 4: buffer 1 x 1 x sqrt(4) = 2.
    units = [1, 3] * 14
    # Reorder point 2 x 4 + 2 = 10; order 2 x 14 + 2 - 10 = 20.
    assert rule(in_stock_units=units, lead_time_days=4, stock_on_hand=10)[0] == 20
    assert rule(in_stock_units=units, lead_time_days=4, stock_on_hand=11)[0] == 0


def test_units_on_order_count_as_stock():
    assert rule(stock_on_hand=2, on_order=4)[0] == 20  # position 6, same as 6 on the shelf
    assert rule(stock_on_hand=2, on_order=5)[0] == 0


def test_too_little_history_falls_back_to_the_reorder_level():
    few = [9] * 6  # 6 in-stock days: not enough for a rate
    assert rule(in_stock_units=few, stock_on_hand=3) == (7, "reorder_level", None)  # 2 x 5 - 3
    assert rule(in_stock_units=few, stock_on_hand=6) == (0, "reorder_level", None)
    assert rule(in_stock_units=[], stock_on_hand=0, reorder_level=0) == (0, "reorder_level", None)
    assert rule(in_stock_units=[2] * 7, stock_on_hand=6)[1] == "recent_sales"  # 7 is enough


def test_nothing_sold_on_in_stock_days_means_no_suggestion():
    assert rule(in_stock_units=[0] * 28, stock_on_hand=0) == (0, "recent_sales", 0.0)


def test_same_day_delivery_needs_no_buffer():
    assert rule(in_stock_units=[1, 3] * 14, lead_time_days=0, stock_on_hand=0)[0] == 20  # 2 x 10


def test_slow_seller_quantity_is_rounded_up_to_whole_units():
    # Every other day: rate 0.5, spread 0.5. Lead 4: buffer 1, reorder point 3.
    units = [1, 0] * 14
    assert rule(in_stock_units=units, lead_time_days=4, stock_on_hand=3)[0] == 5  # 0.5 x 14 + 1 - 3
    assert rule(in_stock_units=units, lead_time_days=4, stock_on_hand=2)[0] == 6
    # Lead 3: buffer 0.866, reorder point 2.366; order 0.5 x 13 + 0.866 - 2 = 5.37 -> 6.
    assert rule(in_stock_units=units, lead_time_days=3, stock_on_hand=2)[0] == 6


# ── Against real records ────────────────────────────────────────────────────


def candidates(org, now: datetime = NOW) -> dict[str, ReorderCandidate]:
    with SessionLocal() as db:
        found = reorder_candidates(db, db.get(Organization, org.id), now)
        return {c.product.name: c for c in found}


@pytest.fixture
def seller(client, headers, make_product):
    """A product created 1 Nov that sold `daily` units every day of the window."""

    def _make(name: str, daily: int, initial_stock: int, **overrides) -> dict:
        product = make_product(name=name, initial_stock=initial_stock, **overrides)
        backdate_product(product, manila(NOV_1, 8))
        for day in WINDOW:
            if daily:
                sell_at(client, headers, [(product, daily)], manila(day, 12))
        return product

    return _make


def test_suggests_from_the_daily_rate_and_explains_it(client, headers, org, seller):
    product = seller("Steady", daily=2, initial_stock=60)  # 60 - 56 = 4 left
    found = candidates(org)["Steady"]
    assert (found.basis, found.daily_rate, found.in_stock_days) == ("recent_sales", 2.0, 28)
    assert (found.lead_time_days, found.lead_time_source) == (3, "store_default")
    assert found.quantity == 2 * 13 - 4
    assert found.product.id.hex == product["id"].replace("-", "")


def test_no_suggestion_while_stock_covers_the_delivery_time(org, seller):
    seller("Well stocked", daily=2, initial_stock=63)  # 7 left > reorder point 6
    assert "Well stocked" not in candidates(org)


def test_empty_shelf_days_do_not_lower_the_rate(client, headers, org, make_product):
    # Sold 4 a day for 14 days, then the shelf was empty for the other 14.
    product = make_product(name="Ran out", initial_stock=56, reorder_level=5)
    backdate_product(product, manila(NOV_1, 8))
    for day in WINDOW[:14]:
        sell_at(client, headers, [(product, 4)], manila(day, 12))
    found = candidates(org)["Ran out"]
    # The 14th day reached zero, so it's a stockout day too: 13 in-stock days at 4 a day.
    assert (found.daily_rate, found.in_stock_days) == (4.0, 13)
    assert found.quantity == 4 * 13  # a plain 28-day average would have said 2 a day: 26


def test_supplier_lead_time_and_open_orders(client, headers, org, seller):
    product = seller("From supplier", daily=2, initial_stock=60)  # 4 left
    sup = client.post(
        "/api/v1/suppliers", json={"name": "Weekly truck", "lead_time_days": 7}, headers=headers
    ).json()
    assert sup["lead_time_days"] == 7
    po = draft(client, headers, [{"product_id": product["id"], "quantity": 5}], sup["id"]).json()

    found = candidates(org)["From supplier"]
    assert (found.lead_time_days, found.lead_time_source) == (7, "supplier")
    assert found.supplier_name == "Weekly truck"
    assert found.on_order == 5
    # Reorder point 2 x 7 = 14 >= position 9; order 2 x 17 - 9 = 25.
    assert found.quantity == 25

    # Cancelled: no longer on order, and its supplier no longer counts.
    assert client.post(f"{PO_URL}/{po['id']}/cancel", headers=headers).status_code == 200
    found = candidates(org)["From supplier"]
    assert (found.on_order, found.lead_time_source) == (0, "store_default")


def test_only_the_undelivered_part_of_an_order_is_on_order(client, headers, org, seller):
    product = seller("Part delivered", daily=2, initial_stock=60)  # 4 left
    sup = client.post("/api/v1/suppliers", json={"name": "S"}, headers=headers).json()
    po = draft(client, headers, [{"product_id": product["id"], "quantity": 10}], sup["id"]).json()
    po = client.post(f"{PO_URL}/{po['id']}/approve", headers=headers).json()
    assert receive(client, headers, po, [3]).status_code == 201  # 3 arrive: 7 on the shelf

    # 7 on the shelf + 7 still to come = 14 > reorder point 6: nothing to order. Counting the
    # whole order (10) or ignoring it would both be wrong; check the number directly.
    assert "Part delivered" not in candidates(org)
    with SessionLocal() as db:
        assert _on_order(db, org.id)[uuid.UUID(product["id"])] == 7


def test_the_latest_orders_supplier_decides_the_lead_time(client, headers, org, seller):
    product = seller("Switched supplier", daily=2, initial_stock=58)  # 2 left + 2 on order
    line = [{"product_id": product["id"], "quantity": 1}]
    for name, lead, created in (("Old", 7, manila(NOV_1, 9)), ("New", 2, manila(WINDOW[5], 9))):
        sup = client.post(
            "/api/v1/suppliers", json={"name": name, "lead_time_days": lead}, headers=headers
        ).json()
        po = draft(client, headers, line, sup["id"]).json()
        with SessionLocal() as db:
            db.execute(
                update(PurchaseOrder).where(PurchaseOrder.id == po["id"]).values(created_at=created)
            )
            db.commit()
    found = candidates(org)["Switched supplier"]
    assert (found.supplier_name, found.lead_time_days) == ("New", 2)


def test_supplier_without_lead_time_and_store_default(client, headers, org, seller):
    product = seller("Default", daily=2, initial_stock=60)
    sup = client.post("/api/v1/suppliers", json={"name": "No lead time"}, headers=headers).json()
    draft(client, headers, [{"product_id": product["id"], "quantity": 1}], sup["id"])
    with SessionLocal() as db:
        db.execute(
            update(Organization).where(Organization.id == org.id).values(default_lead_time_days=5)
        )
        db.commit()
    found = candidates(org)["Default"]
    assert (found.lead_time_days, found.lead_time_source) == (5, "store_default")
    assert found.supplier_name == "No lead time"


def test_new_products_use_the_reorder_level(org, make_product):
    make_product(name="Brand new", initial_stock=2, reorder_level=6)  # created just now
    found = candidates(org, now=datetime.now(UTC))["Brand new"]
    assert (found.basis, found.daily_rate, found.quantity) == ("reorder_level", None, 10)


def test_seven_quiet_days_in_stock_mean_no_suggestion(org, make_product):
    # Created a week before the window ends and never sold: 7 in-stock days at 0 a day is enough
    # history to say nobody is buying it, so even the reorder level isn't used.
    product = make_product(name="Quiet", initial_stock=2, reorder_level=6)
    backdate_product(product, manila(WINDOW[-7], 8))
    assert "Quiet" not in candidates(org)


def test_most_urgent_first(client, headers, org, seller, make_product):
    seller("Two days left", daily=2, initial_stock=60)  # 4 left: 2 days
    seller("One day left", daily=4, initial_stock=116)  # 4 left: 1 day
    make_product(name="Empty", initial_stock=0, reorder_level=3)
    assert list(candidates(org)) == ["Empty", "One day left", "Two days left"]


def test_archived_and_other_stores_products_are_left_out(
    client, headers, other_headers, org, seller
):
    gone = seller("Archived", daily=2, initial_stock=60)
    client.delete(f"/api/v1/products/{gone['id']}", headers=headers)
    client.post(
        "/api/v1/products",
        json={"name": "Theirs", "sku": "T-1", "price": "1.00", "reorder_level": 9},
        headers=other_headers,
    )
    assert candidates(org) == {}


def test_damage_that_empties_the_shelf_counts_as_a_stockout_day(client, headers, org, seller):
    product = seller("Damaged", daily=2, initial_stock=60)  # 4 left
    adjust_at(client, headers, product, -4, manila(WINDOW[-1], 20))
    found = candidates(org)["Damaged"]
    assert found.in_stock_days == 27  # the last day reached zero
    assert found.quantity == 26


# ── Overview and "create purchase order" use it ─────────────────────────────


def test_overview_shows_the_reason_for_each_line(client, headers, make_product):
    make_product(name="Bare shelf", initial_stock=0, reorder_level=5, cost="8.00")
    body = client.get("/api/v1/overview", headers=headers).json()["reorder"]
    assert (body["window_days"], body["cover_days"]) == (28, 10)
    [line] = body["lines"]
    assert {k: line[k] for k in (
        "suggested_quantity", "basis", "daily_rate", "on_order", "lead_time_days",
        "lead_time_source", "supplier_name", "unit_cost",
    )} == {
        "suggested_quantity": 10, "basis": "reorder_level", "daily_rate": None, "on_order": 0,
        "lead_time_days": 3, "lead_time_source": "store_default", "supplier_name": None,
        "unit_cost": "8.00",
    }  # fmt: skip


def test_a_draft_from_suggestions_stops_them_being_suggested_again(client, headers, make_product):
    make_product(name="Bare shelf", initial_stock=0, reorder_level=5)
    assert client.post(f"{PO_URL}/from-reorder", headers=headers).status_code == 201
    assert client.get("/api/v1/overview", headers=headers).json()["reorder"]["lines"] == []
    again = client.post(f"{PO_URL}/from-reorder", headers=headers)
    assert again.status_code == 409  # the 10 on the draft already cover it

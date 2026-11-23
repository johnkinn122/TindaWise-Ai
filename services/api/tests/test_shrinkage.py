"""Stock going missing: count corrections against sales (app/services/shrinkage.py)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import update

from app.db.session import SessionLocal
from app.models import Organization, Role, StockMovement
from app.services.anomalies import dismiss
from app.services.shrinkage import find_losses, is_flagged
from tests.conftest import auth_headers, make_member
from tests.test_demand_history import manila, sell_at

URL = "/api/v1/anomalies"
# Monday 30 Nov 2026, 10:00 Manila. The window is the 56 complete days 5 Oct to 29 Nov.
NOW = datetime(2026, 11, 30, 2, 0, tzinfo=UTC)


def nov(day: int) -> date:
    return date(2026, 11, day)


def move_at(client, headers, product, change: int, when: datetime, reason="adjustment") -> None:
    """A stock movement through the API ("adjustment" is a stock count correction), moved to
    `when`."""
    response = client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"quantity_change": change, "reason": reason},
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


def losses(org, now: datetime = NOW):
    with SessionLocal() as db:
        found, dismissed = find_losses(db, db.get(Organization, org.id), now)
        return [
            (x.product.name, x.missing, x.units_sold, x.last_loss_day) for x in found
        ], dismissed


@pytest.fixture
def seller(client, headers, make_product):
    """A product that sold `sold` units on 1 Nov (500 in stock)."""

    def _make(name: str, sold: int = 100) -> dict:
        product = make_product(name=name, initial_stock=500)
        if sold:
            sell_at(client, headers, [(product, sold)], manila(nov(1), 12))
        return product

    return _make


# ── The rule ────────────────────────────────────────────────────────────────


def test_five_percent_of_sales_plus_one():
    assert is_flagged(5, 99)  # exactly 5% of 100
    assert not is_flagged(4, 99)
    assert is_flagged(3, 56)  # a slow seller: 3 of 57 is 5.3%
    assert not is_flagged(0, 0)  # nothing missing is never flagged
    assert is_flagged(1, 0)  # missing stock of something that never sells


# ── Against real records ────────────────────────────────────────────────────


def test_counts_that_find_stock_missing_are_flagged(client, headers, org, seller):
    product = seller("Coke", sold=100)
    move_at(client, headers, product, -3, manila(nov(10), 18))
    move_at(client, headers, product, -4, manila(nov(24), 18))
    assert losses(org) == ([("Coke", 7, 100, nov(24))], 0)


def test_found_stock_offsets_and_small_losses_are_left_out(client, headers, org, seller):
    product = seller("Offset", sold=100)
    move_at(client, headers, product, -6, manila(nov(10), 18))
    move_at(client, headers, product, 4, manila(nov(24), 18))  # a later count found 4
    small = seller("Small", sold=100)
    move_at(client, headers, small, -4, manila(nov(10), 18))  # 4 of 101: under 5%
    assert losses(org)[0] == []


def test_recorded_damage_is_explained_not_missing(client, headers, org, seller):
    product = seller("Broken", sold=100)
    move_at(client, headers, product, -30, manila(nov(10), 18), reason="damage")
    assert losses(org)[0] == []


def test_only_the_56_complete_days_before_today_count(client, headers, org, seller):
    product = seller("Edges", sold=100)
    move_at(client, headers, product, -20, manila(date(2026, 10, 4), 18))  # 57 days ago
    move_at(client, headers, product, -20, manila(nov(30), 9))  # today, before NOW
    assert losses(org)[0] == []
    move_at(client, headers, product, -6, manila(date(2026, 10, 5), 8))  # first day of the window
    assert losses(org)[0] == [("Edges", 6, 100, date(2026, 10, 5))]  # 6 of 101


def test_sales_outside_the_window_do_not_count(client, headers, org, make_product):
    product = make_product(name="Old sales", initial_stock=500)
    sell_at(client, headers, [(product, 200)], manila(date(2026, 9, 1), 12))
    sell_at(client, headers, [(product, 40)], manila(nov(2), 12))
    move_at(client, headers, product, -3, manila(nov(20), 18))  # 3 of 41: 7.3%
    assert losses(org)[0] == [("Old sales", 3, 40, nov(20))]


def test_largest_share_first(client, headers, org, seller):
    for name, missing in (("Some", 6), ("Most", 20), ("Least", 5)):
        move_at(client, headers, seller(name, sold=99), -missing, manila(nov(20), 18))
    assert [name for name, *_ in losses(org)[0]] == ["Most", "Some", "Least"]


def test_archived_products_and_other_stores_are_left_out(
    client, headers, other_headers, org, other_org, seller
):
    product = seller("Archived", sold=100)
    move_at(client, headers, product, -20, manila(nov(20), 18))
    assert client.delete(f"/api/v1/products/{product['id']}", headers=headers).status_code == 204
    assert losses(org)[0] == []
    assert losses(other_org)[0] == []


def test_the_latest_count_day_follows_the_store_time_zone(client, headers, org, seller):
    product = seller("Late count", sold=100)
    move_at(client, headers, product, -6, manila(nov(20), 23, 30))  # 21 Nov in Tokyo
    assert losses(org)[0][0][3] == nov(20)
    with SessionLocal() as db:
        db.get(Organization, org.id).timezone = "Asia/Tokyo"
        db.commit()
    assert losses(org)[0][0][3] == nov(21)


# ── Dismissing ──────────────────────────────────────────────────────────────


def test_a_dismissal_holds_until_a_later_count_finds_more(client, headers, org, seller):
    product = seller("Coke", sold=100)
    move_at(client, headers, product, -6, manila(nov(10), 18))
    manager = make_member(org, Role.MANAGER)
    with SessionLocal() as db:
        store = db.get(Organization, org.id)
        _, created = dismiss(
            db, store, actor_id=manager.id, product_id=uuid.UUID(product["id"]), day=nov(10),
            kind="shrinkage", note="Recount was wrong", now=NOW,
        )  # fmt: skip
    assert created
    assert losses(org) == ([], 1)
    move_at(client, headers, product, -2, manila(nov(25), 18))  # a later count: more missing
    assert losses(org) == ([("Coke", 8, 100, nov(25))], 0)


# ── The API (real clock) ────────────────────────────────────────────────────


@pytest.fixture
def losing(client, headers, make_product) -> dict:
    """Sold 100 ten days ago; a count five days ago found 9 missing."""
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    product = make_product(name="Coke 1.5L", sku="COKE-15", initial_stock=500)
    sell_at(client, headers, [(product, 100)], manila(today - timedelta(days=10), 12))
    move_at(client, headers, product, -9, manila(today - timedelta(days=5), 18))
    return {"product": product, "day": (today - timedelta(days=5)).isoformat(), "today": today}


def test_the_list_explains_each_product(client, headers, losing):
    body = client.get(URL, headers=headers).json()
    today = losing["today"]
    assert (body["stock_window_first_day"], body["stock_window_last_day"]) == (
        (today - timedelta(days=56)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
    )
    assert (body["stock_window_days"], body["missing_share_threshold"]) == (56, "0.05")
    assert body["stock_losses"] == [
        {
            "product_id": losing["product"]["id"], "name": "Coke 1.5L", "sku": "COKE-15",
            "unit": "pcs", "day": losing["day"], "missing_units": 9, "units_sold": 100,
            "missing_share": "0.0891",
        }
    ]  # fmt: skip
    assert body["stock_losses_dismissed"] == 0


def test_dismissing_is_logged_and_only_the_current_alert_can_be(client, headers, losing):
    body = {"product_id": losing["product"]["id"], "day": losing["day"], "kind": "shrinkage"}
    wrong_day = body | {"day": losing["today"].isoformat()}
    assert client.post(f"{URL}/dismissals", json=wrong_day, headers=headers).status_code == 404

    first = client.post(
        f"{URL}/dismissals", json=body | {"note": "Gave 9 to the church"}, headers=headers
    )
    assert first.status_code == 201, first.text
    assert first.json()["kind"] == "shrinkage"
    assert client.post(f"{URL}/dismissals", json=body, headers=headers).status_code == 200

    listed = client.get(URL, headers=headers).json()
    assert (listed["stock_losses"], listed["stock_losses_dismissed"]) == ([], 1)
    [event] = client.get("/api/v1/audit-events", headers=headers).json()["items"]
    assert event["action"] == "anomaly.dismissed"
    assert event["summary"].startswith(
        "Dismissed a missing-stock alert: Coke 1.5L: 9 pcs missing in stock counts, 8.9% of 100 "
        "sold in 8 weeks (latest count "
    )
    assert {k: event["details"][k] for k in ("kind", "missing", "units_sold", "note")} == {
        "kind": "shrinkage", "missing": 9, "units_sold": 100, "note": "Gave 9 to the church",
    }  # fmt: skip


def test_cashiers_cannot_see_or_dismiss(client, org, losing):
    cashier = auth_headers(org, Role.CASHIER)
    body = {"product_id": losing["product"]["id"], "day": losing["day"], "kind": "shrinkage"}
    assert client.get(URL, headers=cashier).status_code == 403
    assert client.post(f"{URL}/dismissals", json=body, headers=cashier).status_code == 403

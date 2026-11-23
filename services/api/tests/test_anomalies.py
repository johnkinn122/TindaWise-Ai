"""Unusual sales days, the "worth a look" list (app/services/anomalies.py)."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import AnomalyDismissal, AuditEvent, Organization, Product, Role
from app.services.anomalies import Alert, check_day, describe, dismiss, find_alerts
from tests.conftest import auth_headers, make_member
from tests.test_demand_history import backdate_product, manila, sell_at

URL = "/api/v1/anomalies"
NOV_1 = date(2026, 11, 1)
# Monday 30 Nov 2026, 10:00 Manila. The days checked are 23 to 29 Nov.
NOW = datetime(2026, 11, 30, 2, 0, tzinfo=UTC)


def nov(day: int) -> date:
    return date(2026, 11, day)


# ── The rule ────────────────────────────────────────────────────────────────


def test_spike_at_three_times_usual_counting_the_plus_one():
    # Usual 4: (sold + 1) >= 3 x 5, so 14 is a spike (exactly 3x) and 13 isn't.
    assert check_day(14, [4] * 28) == ("spike", 4.0)
    assert check_day(13, [4] * 28) == (None, 4.0)


def test_drop_needs_a_product_that_usually_sells_several_a_day():
    # (usual + 1) >= 7.5 x (sold + 1): selling 0 is a drop from 6.5 a day (exactly 7.5x).
    assert check_day(0, [6, 7] * 7) == ("drop", 6.5)
    assert check_day(0, [6] * 14) == (None, 6.0)
    assert check_day(1, [14] * 14) == ("drop", 14.0)  # 15 >= 7.5 x 2: far below, not only zero


def test_slow_sellers_need_a_real_jump_to_spike():
    usual_half = [1, 0] * 14
    assert check_day(3, usual_half) == (None, 0.5)  # 4 < 3 x 1.5
    assert check_day(4, usual_half) == ("spike", 0.5)
    assert check_day(0, [0] * 28) == (None, 0.0)  # never sells, didn't sell: nothing to see


def test_fewer_than_fourteen_in_stock_days_is_too_little_history():
    assert check_day(50, [2] * 13) == (None, None)
    assert check_day(50, [2] * 14)[0] == "spike"


def test_the_log_summary_reads_like_the_panel():
    coke = Product(name="Coke 1.5L")
    drop = Alert(coke, nov(21), "drop", 0, 9.0, 28)
    spike = Alert(coke, nov(3), "spike", 20, 4.5, 28)
    assert describe(drop) == "Coke 1.5L sold 0 on Nov 21 while in stock (usually about 9 a day)"
    assert describe(spike) == "Coke 1.5L sold 20 on Nov 3 (usually about 4.5 a day)"


# ── Against real records ────────────────────────────────────────────────────


def alerts(org, now: datetime = NOW):
    with SessionLocal() as db:
        found, dismissed = find_alerts(db, db.get(Organization, org.id), now)
        return [(a.product.name, a.day, a.kind, a.units_sold) for a in found], dismissed


@pytest.fixture
def seller(client, headers, make_product):
    """A product created 1 Nov that sold `daily` units every day to 29 Nov, except `days`."""

    def _make(name: str, daily: int, days: dict[int, int] | None = None, **overrides) -> dict:
        product = make_product(name=name, initial_stock=500, **overrides)
        backdate_product(product, manila(NOV_1, 8))
        for n in range(1, 30):
            units = (days or {}).get(n, daily)
            if units:
                sell_at(client, headers, [(product, units)], manila(nov(n), 12))
        return product

    return _make


def test_finds_spikes_and_drops_newest_first(org, seller):
    seller("Steady", daily=4, days={27: 20})  # 21 >= 3 x 5
    seller("Regular", daily=9, days={28: 0})  # 10 >= 7.5 x 1
    seller("Quiet", daily=4)
    found, dismissed = alerts(org)
    assert found == [("Regular", nov(28), "drop", 0), ("Steady", nov(27), "spike", 20)]
    assert dismissed == 0


def test_usual_comes_from_the_in_stock_days_before(org, seller):
    seller("Regular", daily=9, days={28: 0})
    seller("Keeps the store open", daily=1)
    with SessionLocal() as db:
        [alert], _ = find_alerts(db, db.get(Organization, org.id), NOW)
    # The 28 days before 28 Nov are 31 Oct to 27 Nov; 31 Oct is before the product existed.
    assert (alert.usual, alert.in_stock_days) == (9.0, 27)


def test_on_the_same_day_drops_come_before_spikes(org, seller):
    seller("A spike", daily=4, days={29: 20})
    seller("Z drop", daily=9, days={29: 0})
    assert [kind for _, _, kind, _ in alerts(org)[0]] == ["drop", "spike"]


def test_only_the_seven_complete_days_before_today_are_checked(client, headers, org, seller):
    product = seller("Steady", daily=4, days={22: 30})  # 22 Nov: eight days ago
    sell_at(client, headers, [(product, 40)], manila(nov(30), 9))  # today, before NOW
    assert alerts(org)[0] == []


def test_an_empty_shelf_is_not_a_drop(client, headers, org, make_product):
    # 9 a day until the 27th empties the shelf; the 28th and 29th sell nothing because there
    # is nothing to sell.
    product = make_product(name="Ran out", initial_stock=9 * 27)
    backdate_product(product, manila(NOV_1, 8))
    for n in range(1, 28):
        sell_at(client, headers, [(product, 9)], manila(nov(n), 12))
    assert alerts(org)[0] == []


def test_a_day_the_whole_store_sold_nothing_is_not_judged(client, headers, org, make_product):
    # Closed on 28 Nov (no sales at all): one store-level fact, not a drop for every product.
    regulars = [make_product(name=f"Regular {n}", initial_stock=500) for n in range(3)]
    for product in regulars:
        backdate_product(product, manila(NOV_1, 8))
    for n in range(1, 30):
        if n != 28:
            sell_at(client, headers, [(p, 9) for p in regulars], manila(nov(n), 12))
    assert alerts(org)[0] == []


def test_closed_days_are_left_out_of_the_usual(client, headers, org, make_product):
    # Open every other day from 1 to 27 Nov, selling 8. Counting the closed days, the usual would
    # be 4 and selling nothing on the 29th wouldn't be a drop (4 + 1 < 7.5). Without them it's 8,
    # and it is (8 + 1 >= 7.5).
    product = make_product(name="Alternate", initial_stock=500)
    backdate_product(product, manila(NOV_1, 8))
    for n in range(1, 28, 2):
        sell_at(client, headers, [(product, 8)], manila(nov(n), 12))
    other = make_product(name="Keeps the store open", initial_stock=500)
    backdate_product(other, manila(NOV_1, 8))
    sell_at(client, headers, [(other, 1)], manila(nov(29), 12))  # the store was open on the 29th
    with SessionLocal() as db:
        found, _ = find_alerts(db, db.get(Organization, org.id), NOW)
    [drop] = [a for a in found if a.product.name == "Alternate"]
    assert (drop.day, drop.kind, drop.usual, drop.in_stock_days) == (nov(29), "drop", 8.0, 14)


def test_new_products_are_not_judged(client, headers, org, make_product):
    # Created 20 Nov: 8 in-stock days before the 28th, fewer than 14.
    product = make_product(name="New", initial_stock=100)
    backdate_product(product, manila(nov(20), 8))
    for n in range(20, 30):
        sell_at(client, headers, [(product, 30 if n == 28 else 2)], manila(nov(n), 12))
    assert alerts(org)[0] == []


def test_archived_products_and_other_stores_are_left_out(
    client, headers, other_headers, org, other_org, seller
):
    product = seller("Archived", daily=4, days={27: 20})
    assert client.delete(f"/api/v1/products/{product['id']}", headers=headers).status_code == 204
    assert alerts(org)[0] == []
    assert alerts(other_org)[0] == []


def test_store_days_follow_the_store_time_zone(client, headers, org, make_product):
    # 20 sold at 23:30 Manila on 27 Nov is 28 Nov in Tokyo time. The alert follows the zone.
    product = make_product(name="Late", initial_stock=500)
    backdate_product(product, manila(NOV_1, 8))
    for n in range(1, 30):
        sell_at(client, headers, [(product, 4)], manila(nov(n), 12))
    sell_at(client, headers, [(product, 16)], manila(nov(27), 23, 30))
    assert alerts(org)[0] == [("Late", nov(27), "spike", 20)]
    with SessionLocal() as db:
        store = db.get(Organization, org.id)
        store.timezone = "Asia/Tokyo"
        db.commit()
    assert [(day, units) for _, day, _, units in alerts(org)[0]] == [(nov(28), 20)]


# ── Dismissing (service) ────────────────────────────────────────────────────


def test_dismissed_alerts_leave_the_list_and_are_counted(org, seller):
    product = seller("Regular", daily=9, days={28: 0})
    seller("Keeps the store open", daily=1)
    owner = make_member(org, Role.OWNER)
    with SessionLocal() as db:
        store = db.get(Organization, org.id)
        dismissal, created = dismiss(
            db, store, actor_id=owner.id, product_id=uuid.UUID(product["id"]), day=nov(28),
            kind="drop", note="Shop closed for the fiesta", now=NOW,
        )  # fmt: skip
    assert created and dismissal.note == "Shop closed for the fiesta"
    assert alerts(org) == ([], 1)


def test_two_people_dismissing_at_once_store_one_dismissal(org, seller):
    product = seller("Regular", daily=9, days={28: 0})
    seller("Keeps the store open", daily=1)
    people = [make_member(org, Role.MANAGER) for _ in range(4)]

    def attempt(n: int) -> tuple[uuid.UUID, bool]:
        with SessionLocal() as db:
            store = db.get(Organization, org.id)
            dismissal, created = dismiss(
                db, store, actor_id=people[n].id, product_id=uuid.UUID(product["id"]),
                day=nov(28), kind="drop", note=None, now=NOW,
            )  # fmt: skip
            return dismissal.id, created

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(attempt, range(4)))

    assert [created for _, created in outcomes].count(True) == 1
    assert len({dismissal_id for dismissal_id, _ in outcomes}) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AnomalyDismissal)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1


# ── The API (real clock: history is placed relative to today) ───────────────


def store_today() -> date:
    return datetime.now(ZoneInfo("Asia/Manila")).date()


@pytest.fixture
def flagged(client, headers, make_product) -> dict:
    """A product that sells 9 a day and sold nothing, while in stock, the day before yesterday.
    Water sells 1 a day, so the store was open that day."""
    today = store_today()
    product = make_product(name="Coke 1.5L", sku="COKE-15", initial_stock=500)
    water = make_product(name="Water 500ml", sku="WATER-05", initial_stock=500)
    for p in (product, water):
        backdate_product(p, manila(today - timedelta(days=20), 8))
    for n in range(1, 21):
        lines = [(water, 1)] if n == 2 else [(product, 9), (water, 1)]
        sell_at(client, headers, lines, manila(today - timedelta(days=n), 12))
    return {"product": product, "day": (today - timedelta(days=2)).isoformat()}


def dismissal_body(flagged: dict, **overrides) -> dict:
    return {"product_id": flagged["product"]["id"], "day": flagged["day"], "kind": "drop"} | (
        overrides
    )


def test_owner_sees_each_alert_with_its_explanation(client, headers, flagged):
    body = client.get(URL, headers=headers).json()
    today = store_today()
    assert (body["first_day"], body["last_day"]) == (
        (today - timedelta(days=7)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
    )
    assert (body["window_days"], body["spike_multiple"], body["drop_multiple"]) == (
        28,
        "3.0",
        "7.5",
    )
    assert body["timezone"] == "Asia/Manila"
    assert body["alerts"] == [
        {
            "product_id": flagged["product"]["id"], "name": "Coke 1.5L", "sku": "COKE-15",
            "unit": "pcs", "day": flagged["day"], "kind": "drop", "units_sold": 0,
            "usual_daily": "9.0", "in_stock_days": 18,
        }
    ]  # fmt: skip
    assert body["dismissed_count"] == 0


def test_dismissing_is_logged_once_and_a_repeat_returns_the_first(client, headers, org, flagged):
    first = client.post(f"{URL}/dismissals", json=dismissal_body(flagged), headers=headers)
    assert first.status_code == 201, first.text
    assert first.json()["note"] is None  # no note given
    again = client.post(f"{URL}/dismissals", json=dismissal_body(flagged), headers=headers)
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]

    body = client.get(URL, headers=headers).json()
    assert (body["alerts"], body["dismissed_count"]) == ([], 1)
    [event] = client.get("/api/v1/audit-events", headers=headers).json()["items"]
    assert event["action"] == "anomaly.dismissed"
    assert event["entity_id"] == flagged["product"]["id"]
    assert event["summary"].startswith("Dismissed an unusual-sales alert: Coke 1.5L sold 0 on ")
    assert event["summary"].endswith(" while in stock (usually about 9 a day)")
    assert event["details"]["kind"] == "drop" and event["details"]["usual"] == 9.0


def test_a_managers_dismissal_is_theirs_with_the_note(client, org, flagged, headers):
    manager = auth_headers(org, Role.MANAGER)
    response = client.post(
        f"{URL}/dismissals",
        json=dismissal_body(flagged, note="  Delivery truck blocked the door  "),
        headers=manager,
    )
    assert response.status_code == 201
    assert response.json()["note"] == "Delivery truck blocked the door"
    [event] = client.get("/api/v1/audit-events", headers=headers).json()["items"]
    assert event["actor_name"] == "Test manager"


def test_only_an_alert_on_the_list_can_be_dismissed(client, headers, flagged, make_product):
    for body in (
        dismissal_body(flagged, kind="spike"),
        dismissal_body(flagged, day=store_today().isoformat()),
        dismissal_body(flagged, product_id=str(uuid.uuid4())),
        dismissal_body(flagged, product_id=make_product(name="Fine")["id"]),
    ):
        response = client.post(f"{URL}/dismissals", json=body, headers=headers)
        assert response.status_code == 404, body
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AnomalyDismissal)) == 0


def test_bad_requests_are_refused(client, headers, flagged):
    for body in (
        dismissal_body(flagged, kind="weird"),
        dismissal_body(flagged, note="x" * 281),
        dismissal_body(flagged, day="yesterday"),
    ):
        assert client.post(f"{URL}/dismissals", json=body, headers=headers).status_code == 422


def test_cashiers_and_signed_out_visitors_are_refused(client, org, flagged):
    cashier = auth_headers(org, Role.CASHIER)
    assert client.get(URL, headers=cashier).status_code == 403
    assert (
        client.post(f"{URL}/dismissals", json=dismissal_body(flagged), headers=cashier).status_code
        == 403
    )
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/dismissals", json=dismissal_body(flagged)).status_code == 401


def test_another_store_can_neither_see_nor_dismiss_the_alert(client, other_headers, flagged):
    assert client.get(URL, headers=other_headers).json()["alerts"] == []
    response = client.post(f"{URL}/dismissals", json=dismissal_body(flagged), headers=other_headers)
    assert response.status_code == 404

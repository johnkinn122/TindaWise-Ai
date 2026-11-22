from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import update

from app.db.session import SessionLocal
from app.models import Organization, Role, Sale
from app.services.overview import build_overview, suggested_quantity
from tests.conftest import auth_headers

# Saturday 21 Nov 2026, 10:00 in Manila (UTC+8). Its week runs Sun 15 to Sat 21 Nov.
SATURDAY_10AM = datetime(2026, 11, 21, 2, 0, tzinfo=UTC)


def sell(client, headers, product_id, quantity=1):
    response = client.post(
        "/api/v1/sales",
        json={
            "lines": [{"product_id": product_id, "quantity": quantity}],
            "payment_method": "cash",
            "amount_tendered": "10000.00",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def backdate(sale_id: str, when: datetime) -> None:
    with SessionLocal() as db:
        db.execute(update(Sale).where(Sale.id == sale_id).values(created_at=when))
        db.commit()


def overview_at(org: Organization, now: datetime, **kwargs):
    defaults = {"cashier_id": None, "include_costs": True}
    with SessionLocal() as db:
        return build_overview(db, db.get(Organization, org.id), now=now, **defaults | kwargs)


def test_empty_store_has_zeroes_and_a_sunday_to_saturday_week(org):
    result = overview_at(org, SATURDAY_10AM)

    assert result.today.sales == Decimal("0.00")
    assert result.today.transactions == 0
    assert result.today.gross_margin is None  # no sales, no margin (not 0%)
    assert [d.date for d in result.week] == [date(2026, 11, 15 + i) for i in range(7)]
    assert result.timezone == "Asia/Manila"
    assert result.stock_to_watch == []
    assert result.reorder.lines == []


def test_days_follow_the_store_time_zone_not_utc(org, client, headers, make_product):
    product = make_product(price="100.00", cost="75.00", initial_stock=50)
    after_midnight = sell(client, headers, product["id"], 2)  # ₱200
    before_midnight = sell(client, headers, product["id"], 1)  # ₱100
    last_saturday = sell(client, headers, product["id"], 4)  # ₱400
    # 16:30 UTC on Friday is 00:30 Saturday in Manila; 15:30 UTC is still Friday there.
    backdate(after_midnight["id"], datetime(2026, 11, 20, 16, 30, tzinfo=UTC))
    backdate(before_midnight["id"], datetime(2026, 11, 20, 15, 30, tzinfo=UTC))
    backdate(last_saturday["id"], datetime(2026, 11, 14, 5, 0, tzinfo=UTC))

    result = overview_at(org, SATURDAY_10AM)

    assert result.today.sales == Decimal("200.00")
    assert result.today.transactions == 1
    assert result.today.gross_margin == Decimal("0.2500")  # (200 - 150) / 200
    assert result.same_day_last_week.sales == Decimal("400.00")
    friday, saturday = result.week[5], result.week[6]
    assert friday.sales == Decimal("100.00")
    assert saturday.sales == Decimal("200.00")
    assert saturday.last_week_sales == Decimal("400.00")


def test_days_that_have_not_happened_are_null_not_zero(org):
    wednesday = datetime(2026, 11, 18, 4, 0, tzinfo=UTC)
    result = overview_at(org, wednesday)

    assert [d.sales for d in result.week[4:]] == [None, None, None]  # Thu, Fri, Sat
    assert result.week[3].sales == Decimal("0.00")  # today, no sales yet
    assert all(d.last_week_sales == Decimal("0.00") for d in result.week)


def test_cashiers_see_their_own_sales_and_no_costs(client, org, headers, make_product):
    product = make_product(price="50.00", cost="40.00", initial_stock=3, reorder_level=5)
    cashier = auth_headers(org, Role.CASHIER)
    sell(client, headers, product["id"])  # owner's sale
    sell(client, cashier, product["id"])  # cashier's sale

    mine = client.get("/api/v1/overview", headers=cashier).json()
    assert mine["sales_scope"] == "mine"
    assert mine["costs_visible"] is False
    assert mine["today"] == {
        "sales": "50.00",
        "refunds": "0.00",
        "transactions": 1,
        "gross_margin": None,
    }
    assert mine["same_day_last_week"]["gross_margin"] is None
    assert mine["reorder"]["estimated_cost"] is None
    assert all(line["unit_cost"] is None for line in mine["reorder"]["lines"])
    assert "cost" not in str(mine["stock_to_watch"])

    store = client.get("/api/v1/overview", headers=headers).json()
    assert store["sales_scope"] == "store"
    assert store["today"] == {
        "sales": "100.00",
        "refunds": "0.00",
        "transactions": 2,
        "gross_margin": "0.2000",
    }
    assert store["reorder"]["lines"][0]["unit_cost"] == "40.00"


def test_managers_see_the_whole_store(client, org, headers, make_product):
    product = make_product(price="10.00", initial_stock=5)
    sell(client, headers, product["id"])
    manager = auth_headers(org, Role.MANAGER)

    body = client.get("/api/v1/overview", headers=manager).json()
    assert body["sales_scope"] == "store"
    assert body["costs_visible"] is True
    assert body["today"]["transactions"] == 1


def test_stock_to_watch_and_rule_based_reorder_quantities(client, headers, make_product):
    # Fast seller: 13 in stock, 10 sold, so 3 left (level 5). Target max(2 x 5, 10) = 10 → 7.
    fast = make_product(name="Fast seller", initial_stock=13, reorder_level=5, cost="8.00")
    sell(client, headers, fast["id"], 10)
    # Out of stock, never sold: target 2 x 5 = 10 → order 10.
    make_product(name="Bare shelf", initial_stock=0, reorder_level=5, cost="8.00")
    # No reorder level and no sales: watched (out of stock) but no number is made up for it.
    make_product(name="Unknown demand", initial_stock=0, reorder_level=0)
    make_product(name="Plenty", initial_stock=40, reorder_level=5)
    archived = make_product(name="Archived low", initial_stock=1, reorder_level=5)
    client.delete(f"/api/v1/products/{archived['id']}", headers=headers)

    body = client.get("/api/v1/overview", headers=headers).json()

    watched = [(item["name"], item["stock_status"]) for item in body["stock_to_watch"]]
    assert watched == [
        ("Bare shelf", "out_of_stock"),
        ("Unknown demand", "out_of_stock"),
        ("Fast seller", "low_stock"),
    ]
    assert body["out_of_stock_count"] == 2
    assert body["low_stock_count"] == 1

    lines = {line["name"]: line for line in body["reorder"]["lines"]}
    assert set(lines) == {"Bare shelf", "Fast seller"}
    assert lines["Fast seller"]["sold_recently"] == 10
    assert lines["Fast seller"]["suggested_quantity"] == 7
    assert lines["Bare shelf"]["suggested_quantity"] == 10
    assert body["reorder"]["total_count"] == 2
    assert body["reorder"]["lookback_days"] == 14
    assert body["reorder"]["estimated_cost"] == "136.00"  # (10 + 7) x ₱8.00


def test_other_stores_are_never_counted(client, headers, other_headers):
    product = client.post(
        "/api/v1/products",
        json={"name": "Theirs", "sku": "T-1", "price": "99.00", "initial_stock": 0},
        headers=other_headers,
    ).json()
    client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"quantity_change": 5, "reason": "purchase"},
        headers=other_headers,
    )
    sell(client, other_headers, product["id"])

    body = client.get("/api/v1/overview", headers=headers).json()
    assert body["today"]["transactions"] == 0
    assert body["stock_to_watch"] == []


def test_overview_needs_a_session(client):
    assert client.get("/api/v1/overview").status_code == 401


def test_suggested_quantity_rule():
    assert suggested_quantity(stock_on_hand=3, reorder_level=5, sold_recently=0) == 7
    assert suggested_quantity(stock_on_hand=3, reorder_level=5, sold_recently=30) == 27
    assert suggested_quantity(stock_on_hand=0, reorder_level=0, sold_recently=0) == 0
    assert suggested_quantity(stock_on_hand=50, reorder_level=5, sold_recently=4) == 0


def refund_one(client, headers, sale, restock=True):
    response = client.post(
        f"/api/v1/sales/{sale['id']}/refunds",
        json={
            "lines": [{"sale_line_id": sale["lines"][0]["id"], "quantity": 1, "restock": restock}],
            "reason": "customer_return",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_todays_sales_are_net_of_refunds(client, org, headers, make_product):
    product = make_product(price="50.00", cost="40.00", initial_stock=10)
    cashier = auth_headers(org, Role.CASHIER)
    cashier_sale = sell(client, cashier, product["id"], 2)  # 100.00
    owner_sale = sell(client, headers, product["id"], 1)  # 50.00
    refund_one(client, headers, cashier_sale)  # 50.00 back, unit restocked

    store = client.get("/api/v1/overview", headers=headers).json()
    assert store["today"]["sales"] == "100.00"  # 150 - 50
    assert store["today"]["refunds"] == "50.00"
    assert store["today"]["transactions"] == 2
    # Net cost 120 - 40 restocked = 80, so (100 - 80) / 100.
    assert store["today"]["gross_margin"] == "0.2000"

    # The refund belongs to the cashier's sale, so it lowers the cashier's own figures.
    mine = client.get("/api/v1/overview", headers=cashier).json()
    assert (mine["today"]["sales"], mine["today"]["refunds"]) == ("50.00", "50.00")

    refund_one(client, headers, owner_sale, restock=False)
    mine = client.get("/api/v1/overview", headers=cashier).json()
    assert mine["today"]["sales"] == "50.00"  # someone else's sale: not in "mine"


def test_refunded_units_are_not_counted_as_recent_demand(client, headers, make_product):
    # 10 in stock, 10 sold, 4 refunded and restocked → 4 left (level 4), recent demand 6.
    fast = make_product(name="Fast seller", initial_stock=10, reorder_level=4)
    sale = sell(client, headers, fast["id"], 10)
    client.post(
        f"/api/v1/sales/{sale['id']}/refunds",
        json={
            "lines": [{"sale_line_id": sale["lines"][0]["id"], "quantity": 4}],
            "reason": "wrong_item",
        },
        headers=headers,
    )
    [line] = client.get("/api/v1/overview", headers=headers).json()["reorder"]["lines"]
    assert line["sold_recently"] == 6
    # max(2 x 4, 6) - 4 = 4. Counting the refunded units as demand would give max(8, 10) - 4 = 6.
    assert line["suggested_quantity"] == 4

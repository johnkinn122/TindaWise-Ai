from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.core.errors import InvalidInputError
from app.db.session import SessionLocal
from app.models import Organization, Role, Sale
from app.services.reports import (
    build_sales_report,
    granularity_for,
    previous_period,
    resolve_period,
)
from tests.conftest import auth_headers

URL = "/api/v1/reports/sales"
SUNDAY = date(2026, 11, 22)
# Sunday 22 Nov 2026, 10:00 in Manila.
NOW = datetime(2026, 11, 22, 2, 0, tzinfo=UTC)


def sell(client, headers, lines, method="cash", when=None):
    body = {
        "lines": [{"product_id": p["id"], "quantity": q} for p, q in lines],
        "payment_method": method,
    }
    body |= {"amount_tendered": "100000.00"} if method == "cash" else {"payment_reference": "GC-1"}
    response = client.post("/api/v1/sales", json=body, headers=headers)
    assert response.status_code == 201, response.text
    sale = response.json()
    if when:
        with SessionLocal() as db:
            db.execute(update(Sale).where(Sale.id == sale["id"]).values(created_at=when))
            db.commit()
    return sale


def report(org, **kwargs):
    with SessionLocal() as db:
        return build_sales_report(db, db.get(Organization, org.id), now=NOW, **kwargs)


# ── Periods ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("preset", "start", "end"),
    [
        ("today", date(2026, 11, 22), date(2026, 11, 22)),
        ("yesterday", date(2026, 11, 21), date(2026, 11, 21)),
        ("last_7_days", date(2026, 11, 16), date(2026, 11, 22)),
        ("last_30_days", date(2026, 10, 24), date(2026, 11, 22)),
        ("this_month", date(2026, 11, 1), date(2026, 11, 22)),
        ("last_month", date(2026, 10, 1), date(2026, 10, 31)),
    ],
)
def test_presets_resolve_in_store_days(preset, start, end):
    period = resolve_period(SUNDAY, preset, None, None)
    assert (period.start, period.end) == (start, end)


def test_previous_period_has_the_same_length_and_ends_the_day_before():
    period = resolve_period(SUNDAY, "this_month", None, None)  # 22 days
    previous = previous_period(period)
    assert (previous.start, previous.end, previous.days) == (
        date(2026, 10, 10),
        date(2026, 10, 31),
        22,
    )


def test_custom_ranges_are_checked():
    assert resolve_period(SUNDAY, "today", date(2026, 1, 1), date(2026, 1, 31)).days == 31
    with pytest.raises(InvalidInputError):
        resolve_period(SUNDAY, None, date(2026, 2, 1), date(2026, 1, 1))  # end before start
    with pytest.raises(InvalidInputError):
        resolve_period(SUNDAY, None, date(2024, 1, 1), date(2026, 1, 1))  # over a year
    with pytest.raises(InvalidInputError):
        resolve_period(SUNDAY, None, date(2026, 1, 1), None)  # only one end


@pytest.mark.parametrize(
    ("days", "granularity"), [(1, "day"), (31, "day"), (32, "week"), (182, "week"), (183, "month")]
)
def test_granularity_follows_the_range_length(days, granularity):
    assert granularity_for(days) == granularity


# ── Figures ─────────────────────────────────────────────────────────────────


def test_summary_compares_with_the_previous_period(org, client, headers, make_product):
    soap = make_product(name="Soap", price="40.00", cost="30.00", initial_stock=100)
    sell(client, headers, [(soap, 3)], when=datetime(2026, 11, 20, 4, 0, tzinfo=UTC))  # ₱120
    sell(client, headers, [(soap, 1)], when=datetime(2026, 11, 22, 1, 0, tzinfo=UTC))  # ₱40
    sell(
        client, headers, [(soap, 2)], when=datetime(2026, 11, 12, 4, 0, tzinfo=UTC)
    )  # previous week

    result = report(org, preset="last_7_days")

    assert result.summary.sales == Decimal("160.00")
    assert result.summary.transactions == 2
    assert result.summary.average_sale == Decimal("80.00")
    assert result.summary.gross_profit == Decimal("40.00")
    assert result.summary.gross_margin == Decimal("0.2500")
    assert result.summary.items_sold == 4
    assert result.previous_summary.sales == Decimal("80.00")
    assert result.previous_period.start == date(2026, 11, 9)


def test_days_are_store_days_and_buckets_are_zero_filled(org, client, headers, make_product):
    item = make_product(price="10.00", initial_stock=100)
    # 16:30 UTC on Friday the 20th is 00:30 Saturday the 21st in Manila.
    sell(client, headers, [(item, 1)], when=datetime(2026, 11, 20, 16, 30, tzinfo=UTC))

    result = report(org, preset="last_7_days")

    assert result.granularity == "day"
    assert [p.start for p in result.series] == [date(2026, 11, d) for d in range(16, 23)]
    by_day = {p.start: p.sales for p in result.series}
    assert by_day[date(2026, 11, 21)] == Decimal("10.00")
    assert by_day[date(2026, 11, 20)] == Decimal("0.00")


def test_long_ranges_group_by_week_and_month(org, client, headers, make_product):
    item = make_product(price="10.00", initial_stock=100)
    sell(client, headers, [(item, 2)], when=datetime(2026, 10, 7, 4, 0, tzinfo=UTC))

    weekly = report(org, start=date(2026, 10, 1), end=date(2026, 11, 22))
    assert weekly.granularity == "week"
    assert weekly.series[0].start == date(2026, 9, 27)  # the Sunday the first week starts on
    assert {p.start: p.sales for p in weekly.series}[date(2026, 10, 4)] == Decimal("20.00")

    monthly = report(org, start=date(2026, 1, 1), end=date(2026, 11, 22))
    assert monthly.granularity == "month"
    assert [p.start.month for p in monthly.series] == list(range(1, 12))
    assert monthly.series[9].sales == Decimal("20.00")


def test_top_products_sort_and_count(org, client, headers, make_product):
    cheap = make_product(name="Candy", price="1.00", cost="0.20", initial_stock=500)
    dear = make_product(name="Rice 5kg", price="300.00", cost="280.00", initial_stock=50)
    sell(client, headers, [(cheap, 200), (dear, 2)], when=datetime(2026, 11, 21, 4, 0, tzinfo=UTC))

    by_sales = report(org, preset="last_7_days")
    assert [p.name for p in by_sales.products] == ["Rice 5kg", "Candy"]  # ₱600 vs ₱200
    assert by_sales.product_count == 2
    assert by_sales.products[1].gross_margin == Decimal("0.8000")

    by_profit = report(org, preset="last_7_days", product_sort="gross_profit")
    assert [p.name for p in by_profit.products] == ["Candy", "Rice 5kg"]  # ₱160 vs ₱40
    by_quantity = report(org, preset="last_7_days", product_sort="quantity")
    assert by_quantity.products[0].quantity == 200
    only_one = report(org, preset="last_7_days", top=1)
    assert (len(only_one.products), only_one.product_count) == (1, 2)


def test_categories_and_payment_methods(org, client, headers, make_product):
    category = client.post("/api/v1/categories", json={"name": "Snacks"}, headers=headers).json()
    chips = make_product(name="Chips", price="20.00", category_id=category["id"], initial_stock=50)
    loose = make_product(name="Ice", price="5.00", initial_stock=50)
    when = datetime(2026, 11, 21, 4, 0, tzinfo=UTC)
    sell(client, headers, [(chips, 3)], when=when)
    sell(client, headers, [(loose, 2)], method="e_wallet", when=when)

    result = report(org, preset="last_7_days")
    assert [(c.name, c.sales) for c in result.categories] == [
        ("Snacks", Decimal("60.00")),
        ("No category", Decimal("10.00")),
    ]
    assert [(p.method, p.sales, p.transactions) for p in result.payments] == [
        ("cash", Decimal("60.00"), 1),
        ("e_wallet", Decimal("10.00"), 1),
    ]


def test_purchases_by_supplier_count_received_stock_in_the_period(
    org, client, headers, make_product
):
    item = make_product(initial_stock=0)
    supplier = client.post("/api/v1/suppliers", json={"name": "Puregold"}, headers=headers).json()
    po = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "lines": [{"product_id": item["id"], "quantity": 10, "unit_cost": "7.50"}],
        },
        headers=headers,
    ).json()
    client.post(f"/api/v1/purchase-orders/{po['id']}/approve", headers=headers)
    line = po["lines"][0]["id"]
    client.post(
        f"/api/v1/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": line, "quantity": 4}]},
        headers=headers,
    )

    body = client.get(URL, params={"preset": "today"}, headers=headers).json()
    assert body["suppliers"] == [
        {
            "supplier_id": supplier["id"],
            "name": "Puregold",
            "received_value": "30.00",
            "deliveries": 1,
        }
    ]
    assert body["purchases_total"] == "30.00"


# ── Access ──────────────────────────────────────────────────────────────────


def test_endpoint_defaults_and_validation(client, headers):
    body = client.get(URL, headers=headers).json()
    assert body["period"]["days"] == 7
    assert body["summary"]["average_sale"] is None
    assert client.get(URL, params={"preset": "forever"}, headers=headers).status_code == 422
    bad = client.get(URL, params={"start": "2026-02-01", "end": "2026-01-01"}, headers=headers)
    assert bad.status_code == 422
    assert bad.json()["error"]["fields"] == {"end": "Before the start"}


def test_cashiers_cannot_open_reports_and_stores_are_isolated(
    client, org, headers, other_headers, make_product
):
    assert client.get(URL, headers=auth_headers(org, Role.CASHIER)).status_code == 403
    item = make_product(price="10.00", initial_stock=5)
    sell(client, headers, [(item, 1)])
    theirs = client.get(URL, params={"preset": "today"}, headers=other_headers).json()
    assert theirs["summary"]["transactions"] == 0
    assert theirs["products"] == []

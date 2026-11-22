"""The store-wide inventory ledger and stock summary (GET /api/v1/inventory/...)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from app.db.session import SessionLocal
from app.models import Role, StockMovement, User
from app.schemas.auth import LoginRequest
from app.services.auth import login
from tests.conftest import TEST_PASSWORD, auth_headers, make_member
from tests.test_inventory import adjust
from tests.test_purchase_orders import approved_order, receive
from tests.test_refunds import refund
from tests.test_sales import sell

URL = "/api/v1/inventory"


def ledger(client, headers, **params):
    response = client.get(f"{URL}/movements", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def sign_in(user: User) -> dict[str, str]:
    with SessionLocal() as db:
        _, token = login(db, LoginRequest(email=user.email, password=TEST_PASSWORD))
    return {"Authorization": f"Bearer {token}"}


def set_created_at(movement_id: str, when: datetime) -> None:
    with SessionLocal() as db:
        db.execute(
            update(StockMovement).where(StockMovement.id == movement_id).values(created_at=when)
        )
        db.commit()


# ── The ledger ──────────────────────────────────────────────────────────────


def test_every_kind_of_movement_shows_newest_first_with_its_source(client, headers, make_product):
    noodles = make_product(name="Pancit Canton", sku="NDL-1", price="16.00", initial_stock=10)
    adjust(client, headers, noodles["id"], -1, "damage")
    sale = sell(client, headers, [{"product_id": noodles["id"], "quantity": 3}]).json()
    assert refund(client, headers, sale, [(0, 1)]).status_code == 201
    po = approved_order(client, headers, [{"product_id": noodles["id"], "quantity": 12}])
    assert receive(client, headers, po, [12]).status_code == 201

    page = ledger(client, headers)
    reasons = [item["reason"] for item in page["items"]]
    assert reasons == ["purchase", "return", "sale", "damage", "initial"]
    assert page["total"] == 5
    assert [item["balance_after"] for item in page["items"]] == [19, 7, 6, 9, 10]
    assert [item["quantity_change"] for item in page["items"]] == [12, 1, -3, -1, 10]

    purchase, returned, sold, damaged, opening = page["items"]
    assert purchase["source"] == {"kind": "purchase_order", "id": po["id"], "code": po["code"]}
    # A refund links to its receipt, where refunds are shown.
    assert returned["source"] == {"kind": "refund", "id": sale["id"], "code": "R-000001"}
    assert sold["source"] == {"kind": "sale", "id": sale["id"], "code": sale["receipt_code"]}
    assert damaged["source"] is None and opening["source"] is None

    assert sold["product_name"] == "Pancit Canton"
    assert (sold["sku"], sold["unit"]) == ("NDL-1", "pcs")
    assert sold["created_by_name"] == "Test owner"


def test_filter_by_reason_product_and_search(client, headers, make_product):
    noodles = make_product(name="Pancit Canton", sku="NDL-1")
    soap = make_product(name="Safeguard 50% off", sku="SOAP_1")
    adjust(client, headers, noodles["id"], -2, "damage")
    adjust(client, headers, soap["id"], 3, "adjustment")

    assert [i["quantity_change"] for i in ledger(client, headers, reason="damage")["items"]] == [-2]
    by_product = ledger(client, headers, product_id=soap["id"])
    assert {i["product_id"] for i in by_product["items"]} == {soap["id"]}
    assert by_product["total"] == 2

    assert ledger(client, headers, q="canton")["total"] == 2  # name, any case
    assert ledger(client, headers, q="soap_")["total"] == 2  # SKU
    # LIKE wildcards are literal text: "%" alone matches only names that contain "%".
    assert {i["product_name"] for i in ledger(client, headers, q="%")["items"]} == {
        "Safeguard 50% off"
    }
    assert ledger(client, headers, q="  ")["total"] == 4  # blank search = no search


def test_filter_by_who_made_the_change(client, org, headers, make_product):
    product = make_product()
    manager = make_member(org, Role.MANAGER)
    adjust(client, sign_in(manager), product["id"], -1, "damage")

    mine = ledger(client, headers, user_id=str(manager.id))
    assert [i["reason"] for i in mine["items"]] == ["damage"]
    assert mine["items"][0]["created_by_name"] == "Test manager"


def test_dates_are_store_days(client, headers, make_product):
    """Asia/Manila is UTC+8: 16:30 UTC on Nov 21 is 00:30 on Nov 22 in the store."""
    product = make_product(initial_stock=5)
    adjust(client, headers, product["id"], 1, "adjustment")
    late, early = ledger(client, headers)["items"]
    set_created_at(early["id"], datetime(2026, 11, 21, 15, 59, tzinfo=UTC))  # Nov 21, 23:59
    set_created_at(late["id"], datetime(2026, 11, 21, 16, 30, tzinfo=UTC))  # Nov 22, 00:30

    nov_22 = ledger(client, headers, start="2026-11-22", end="2026-11-22")
    assert [i["id"] for i in nov_22["items"]] == [late["id"]]
    nov_21 = ledger(client, headers, end="2026-11-21")
    assert [i["id"] for i in nov_21["items"]] == [early["id"]]
    assert ledger(client, headers, start="2026-11-21")["total"] == 2


def test_end_before_start_is_explained(client, headers):
    response = client.get(
        f"{URL}/movements", params={"start": "2026-11-22", "end": "2026-11-21"}, headers=headers
    )
    assert response.status_code == 422
    assert "before the start" in response.text


def test_pages(client, headers, make_product):
    product = make_product()
    for _ in range(4):
        adjust(client, headers, product["id"], 1, "adjustment")
    first = ledger(client, headers, limit=2)
    second = ledger(client, headers, limit=2, offset=2)
    third = ledger(client, headers, limit=2, offset=4)
    assert first["total"] == 5
    assert [len(p["items"]) for p in (first, second, third)] == [2, 2, 1]
    seen = [i["id"] for p in (first, second, third) for i in p["items"]]
    assert len(set(seen)) == 5


# ── The summary ─────────────────────────────────────────────────────────────


def test_summary_counts_active_products_at_current_cost(client, headers, make_product):
    make_product(cost="13.50", reorder_level=5, initial_stock=10)  # in stock
    make_product(cost="68.00", reorder_level=5, initial_stock=3)  # low
    make_product(cost="2.25", reorder_level=5, initial_stock=0)  # out
    archived = make_product(cost="100.00", initial_stock=50)
    assert client.delete(f"/api/v1/products/{archived['id']}", headers=headers).status_code == 204

    summary = client.get(f"{URL}/summary", headers=headers).json()
    assert summary["products"] == 3
    assert summary["units_on_hand"] == 13
    assert summary["stock_value"] == "339.00"  # 10 x 13.50 + 3 x 68.00
    assert summary["currency"] == "PHP"
    assert (summary["low_stock"], summary["out_of_stock"]) == (1, 1)
    assert [p["name"] for p in summary["people"]] == ["Test owner"]


def test_people_are_those_who_changed_stock(client, org, headers, make_product):
    product = make_product()
    cashier = make_member(org, Role.CASHIER)

    def names() -> list[str]:
        summary = client.get(f"{URL}/summary", headers=headers).json()
        return [person["name"] for person in summary["people"]]

    assert names() == ["Test owner"]  # the cashier hasn't sold anything yet
    sale = sell(client, sign_in(cashier), [{"product_id": product["id"], "quantity": 1}])
    assert sale.status_code == 201
    assert names() == ["Test cashier", "Test owner"]


def test_empty_store_summary(client, headers):
    summary = client.get(f"{URL}/summary", headers=headers).json()
    assert summary["products"] == 0
    assert summary["units_on_hand"] == 0
    assert summary["stock_value"] == "0.00"


# ── Access ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/movements", "/summary"])
def test_cashiers_cannot_see_the_ledger_or_stock_value(client, org, path):
    cashier = auth_headers(org, Role.CASHIER)
    assert client.get(f"{URL}{path}", headers=cashier).status_code == 403
    manager = auth_headers(org, Role.MANAGER)
    assert client.get(f"{URL}{path}", headers=manager).status_code == 200


def test_signed_out_is_refused(client):
    assert client.get(f"{URL}/movements").status_code == 401


def test_other_stores_movements_are_invisible(client, headers, other_headers, make_product):
    product = make_product(initial_stock=7)
    assert ledger(client, other_headers)["total"] == 0
    assert ledger(client, other_headers, product_id=product["id"])["total"] == 0
    other = client.get(f"{URL}/summary", headers=other_headers).json()
    assert other["units_on_hand"] == 0
    assert other["people"] == []  # nobody there has changed stock, and ours aren't listed

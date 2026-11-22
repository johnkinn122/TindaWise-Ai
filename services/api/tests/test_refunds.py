import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, InsufficientStockError
from app.db.session import SessionLocal
from app.models import Product, Refund, Role, SaleLine, StockMovement
from app.schemas.sale import RefundCreate, RefundLineCreate, SaleCreate, SaleLineCreate
from app.services.refunds import create_refund
from app.services.sales import create_sale
from tests.conftest import auth_headers, make_member
from tests.test_sales import sell, stock


def refund(client, headers, sale, items, *, reason="customer_return", key=None, **extra):
    """`items` is [(line index, quantity)] or [(line index, quantity, restock)]."""
    lines = [
        {
            "sale_line_id": sale["lines"][item[0]]["id"],
            "quantity": item[1],
            "restock": item[2] if len(item) > 2 else True,
        }
        for item in items
    ]
    hdrs = headers | ({"Idempotency-Key": key} if key else {})
    return client.post(
        f"/api/v1/sales/{sale['id']}/refunds",
        json={"lines": lines, "reason": reason} | extra,
        headers=hdrs,
    )


def refund_count() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Refund)) or 0


@pytest.fixture
def receipt(client, headers, make_product):
    """A receipt: 3 x noodles at 16.00 (cost 13.50) and 2 x soda at 80.00 (cost 68.00)."""
    noodles = make_product(name="Pancit Canton", price="16.00", cost="13.50", initial_stock=10)
    soda = make_product(name="Coke 1.5L", price="80.00", cost="68.00", initial_stock=5)
    sale = sell(
        client,
        headers,
        [{"product_id": noodles["id"], "quantity": 3}, {"product_id": soda["id"], "quantity": 2}],
    ).json()
    return {"sale": sale, "noodles": noodles, "soda": soda}


# ── The happy path ──────────────────────────────────────────────────────────


def test_partial_refund_pays_back_receipt_prices_and_restocks(client, headers, receipt):
    sale, noodles = receipt["sale"], receipt["noodles"]
    response = refund(client, headers, sale, [(0, 2)])

    assert response.status_code == 201
    body = response.json()
    assert body["refunded_total"] == "32.00"  # 2 x 16.00
    assert body["refund_status"] == "partial"
    assert [line["quantity_refunded"] for line in body["lines"]] == [2, 0]
    [r] = body["refunds"]
    assert r["refund_code"] == "R-000001"
    assert r["total"] == "32.00"
    assert r["payment_method"] == "cash"
    assert r["lines"][0] | {"sale_line_id": None} == {
        "sale_line_id": None,
        "product_id": noodles["id"],
        "product_name": "Pancit Canton",
        "unit": "pcs",
        "quantity": 2,
        "unit_price": "16.00",
        "line_total": "32.00",
        "restocked": True,
    }
    assert r["refunded_by_name"] == "Test owner"
    assert "restocked_cost" not in r and "unit_cost" not in r["lines"][0]
    assert stock(client, headers, noodles["id"]) == 9  # 10 - 3 sold + 2 back


def test_restocked_units_are_a_return_in_the_stock_history(client, headers, receipt):
    body = refund(client, headers, receipt["sale"], [(1, 1)]).json()
    with SessionLocal() as db:
        movement = db.scalar(select(StockMovement).where(StockMovement.reason == "return"))
        assert movement.quantity_change == 1
        assert movement.balance_after == 4
        assert str(movement.refund_id) == body["refunds"][0]["id"]
        assert movement.note == "Refund R-000001 on S-000001"


def test_units_not_restocked_leave_stock_alone(client, headers, receipt):
    response = refund(client, headers, receipt["sale"], [(1, 1, False)], reason="damaged")
    assert response.status_code == 201
    assert response.json()["refunds"][0]["lines"][0]["restocked"] is False
    assert stock(client, headers, receipt["soda"]["id"]) == 3  # unchanged after the sale
    with SessionLocal() as db:
        saved = db.scalar(select(Refund))
        assert saved.total == Decimal("80.00")
        assert saved.restocked_cost == Decimal("0.00")  # the cost stays a loss
        assert db.scalar(select(func.count()).where(StockMovement.reason == "return")) == 0


def test_restocked_cost_counts_only_restocked_units(client, headers, receipt):
    refund(client, headers, receipt["sale"], [(0, 3), (1, 1, False)])
    with SessionLocal() as db:
        saved = db.scalar(select(Refund))
        assert saved.total == Decimal("128.00")  # 48 + 80
        assert saved.restocked_cost == Decimal("40.50")  # 3 x 13.50; the soda isn't restocked


def test_refunds_add_up_to_a_full_refund_then_stop(client, headers, receipt):
    sale = receipt["sale"]
    refund(client, headers, sale, [(0, 1)])
    refund(client, headers, sale, [(0, 2), (1, 2)])
    full = client.get(f"/api/v1/sales/{sale['id']}", headers=headers).json()
    assert full["refunded_total"] == full["total"] == "208.00"
    assert full["refund_status"] == "full"
    assert [r["refund_code"] for r in full["refunds"]] == ["R-000001", "R-000002"]

    again = refund(client, headers, sale, [(0, 1)])
    assert again.status_code == 409
    assert again.json()["error"]["fields"] == {sale["lines"][0]["id"]: "Already fully refunded"}


def test_price_changes_after_the_sale_dont_change_the_refund(client, headers, receipt):
    noodles = receipt["noodles"]
    client.patch(f"/api/v1/products/{noodles['id']}", json={"price": "99.00"}, headers=headers)
    body = refund(client, headers, receipt["sale"], [(0, 1)]).json()
    assert body["refunds"][0]["total"] == "16.00"


def test_archived_products_can_still_be_refunded_and_restocked(client, headers, receipt):
    soda = receipt["soda"]
    assert client.delete(f"/api/v1/products/{soda['id']}", headers=headers).status_code == 204
    assert refund(client, headers, receipt["sale"], [(1, 2)]).status_code == 201
    with SessionLocal() as db:
        assert db.get(Product, uuid.UUID(soda["id"])).stock_on_hand == 5


def test_e_wallet_refunds_go_back_to_the_e_wallet(client, headers, make_product):
    item = make_product(price="50.00")
    sale = sell(
        client,
        headers,
        [{"product_id": item["id"], "quantity": 1}],
        payment_method="e_wallet",
        payment_reference="GC-123",
        amount_tendered=None,
    ).json()
    body = refund(client, headers, sale, [(0, 1)]).json()
    assert body["refunds"][0]["payment_method"] == "e_wallet"


# ── Refused requests ────────────────────────────────────────────────────────


def test_refunding_more_than_was_sold_records_nothing(client, headers, receipt):
    sale = receipt["sale"]
    response = refund(client, headers, sale, [(0, 1), (1, 3)])
    assert response.status_code == 409
    assert response.json()["error"]["fields"] == {sale["lines"][1]["id"]: "Only 2 left to refund"}
    assert refund_count() == 0
    assert stock(client, headers, receipt["noodles"]["id"]) == 7  # the valid line wasn't applied


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"lines": [], "reason": "customer_return"}, "lines"),
        ({"lines": "LINE", "reason": "other"}, "request"),  # other without a note
        ({"lines": "LINE", "reason": "free stuff"}, "reason"),
        ({"lines": "LINE", "reason": "other", "note": "   "}, "note"),
    ],
)
def test_invalid_refund_requests(client, headers, receipt, body, field):
    sale = receipt["sale"]
    if body["lines"] == "LINE":
        body = body | {"lines": [{"sale_line_id": sale["lines"][0]["id"], "quantity": 1}]}
    response = client.post(f"/api/v1/sales/{sale['id']}/refunds", json=body, headers=headers)
    assert response.status_code == 422
    assert field in response.json()["error"]["fields"]


def test_other_reason_with_a_note_is_accepted(client, headers, receipt):
    response = refund(client, headers, receipt["sale"], [(0, 1)], reason="other", note=" Promo ")
    assert response.status_code == 201
    assert response.json()["refunds"][0]["note"] == "Promo"


def test_repeated_or_foreign_lines_are_refused(client, headers, receipt, make_product):
    sale = receipt["sale"]
    repeated = refund(client, headers, sale, [(0, 1), (0, 1)])
    assert repeated.status_code == 422

    other_item = make_product(initial_stock=5)
    other_sale = sell(client, headers, [{"product_id": other_item["id"], "quantity": 1}]).json()
    response = client.post(
        f"/api/v1/sales/{sale['id']}/refunds",
        json={
            "lines": [{"sale_line_id": other_sale["lines"][0]["id"], "quantity": 1}],
            "reason": "customer_return",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {
        other_sale["lines"][0]["id"]: "Not on this receipt"
    }
    assert refund_count() == 0


def test_only_owners_and_managers_can_refund(client, org, headers, make_product):
    item = make_product(initial_stock=5)
    cashier = auth_headers(org, Role.CASHIER)
    sale = sell(client, cashier, [{"product_id": item["id"], "quantity": 2}]).json()

    assert refund(client, cashier, sale, [(0, 1)]).status_code == 403
    manager = auth_headers(org, Role.MANAGER)
    assert refund(client, manager, sale, [(0, 1)]).status_code == 201

    # The cashier can still read the refund on their own receipt.
    seen = client.get(f"/api/v1/sales/{sale['id']}", headers=cashier).json()
    assert seen["refunds"][0]["refunded_by_name"] == "Test manager"


def test_other_stores_cannot_refund_your_sales(client, headers, other_headers, receipt):
    assert refund(client, other_headers, receipt["sale"], [(0, 1)]).status_code == 404
    missing = {"id": str(uuid.uuid4()), "lines": receipt["sale"]["lines"]}
    assert refund(client, headers, missing, [(0, 1)]).status_code == 404
    assert refund_count() == 0


# ── Retries and races ───────────────────────────────────────────────────────


def test_retried_refund_pays_out_once(client, headers, receipt):
    sale = receipt["sale"]
    first = refund(client, headers, sale, [(0, 2)], key="rf-1")
    again = refund(client, headers, sale, [(0, 2)], key="rf-1")
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["refunded_total"] == "32.00"
    assert refund_count() == 1
    assert stock(client, headers, receipt["noodles"]["id"]) == 9


def test_a_key_used_on_one_receipt_cant_be_reused_on_another(client, headers, receipt):
    refund(client, headers, receipt["sale"], [(0, 1)], key="rf-2")
    other = sell(client, headers, [{"product_id": receipt["soda"]["id"], "quantity": 1}]).json()
    response = refund(client, headers, other, [(0, 1)], key="rf-2")
    assert response.status_code == 409
    assert refund_count() == 1


def test_refund_numbers_are_sequential_per_store(
    client, headers, other_headers, receipt, make_product
):
    first = refund(client, headers, receipt["sale"], [(0, 1)]).json()
    second = refund(client, headers, receipt["sale"], [(1, 1)]).json()
    assert [r["refund_code"] for r in second["refunds"]] == ["R-000001", "R-000002"]
    assert len(first["refunds"]) == 1

    # Another store's first refund is R-000001 too.
    theirs = client.post(
        "/api/v1/products",
        json={"name": "Theirs", "sku": "T-1", "price": "5.00", "cost": "4.00", "initial_stock": 3},
        headers=other_headers,
    ).json()
    their_sale = sell(client, other_headers, [{"product_id": theirs["id"], "quantity": 1}]).json()
    body = refund(client, other_headers, their_sale, [(0, 1)]).json()
    assert body["refunds"][0]["refund_code"] == "R-000001"


def test_concurrent_refunds_never_refund_the_same_units_twice(org, client, headers, receipt):
    """4 registers try to refund 2 of the 3 noodles on one receipt at the same moment.

    The sale row lock serializes them: exactly one succeeds, the rest see "only 1 left"."""
    sale = receipt["sale"]
    manager = make_member(org, Role.MANAGER)
    line_id = uuid.UUID(sale["lines"][0]["id"])

    def attempt(_: int) -> str:
        data = RefundCreate(
            lines=[RefundLineCreate(sale_line_id=line_id, quantity=2)], reason="customer_return"
        )
        with SessionLocal() as db:
            try:
                create_refund(
                    db, org_id=org.id, sale_id=uuid.UUID(sale["id"]), data=data, user_id=manager.id
                )
                return "ok"
            except ConflictError:
                return "refused"

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(attempt, range(4)))

    assert outcomes.count("ok") == 1
    assert outcomes.count("refused") == 3
    with SessionLocal() as db:
        assert db.get(SaleLine, line_id).quantity_refunded == 2
        assert db.get(Product, uuid.UUID(receipt["noodles"]["id"])).stock_on_hand == 9
    assert refund_count() == 1


def test_refunds_and_checkouts_on_the_same_product_dont_deadlock(
    org, client, headers, make_product
):
    """Refunds (sale -> product -> org locks) and checkouts (product -> org) run together."""
    item = make_product(initial_stock=6)
    cashier = make_member(org, Role.CASHIER)
    sales = [
        sell(client, headers, [{"product_id": item["id"], "quantity": 1}]).json() for _ in range(4)
    ]  # stock now 2

    def work(i: int) -> str:
        with SessionLocal() as db:
            try:
                if i % 2:
                    sale = sales[i // 2]
                    create_refund(
                        db,
                        org_id=org.id,
                        sale_id=uuid.UUID(sale["id"]),
                        data=RefundCreate(
                            lines=[
                                RefundLineCreate(
                                    sale_line_id=uuid.UUID(sale["lines"][0]["id"]), quantity=1
                                )
                            ],
                            reason="customer_return",
                        ),
                        user_id=cashier.id,
                    )
                    return "refunded"
                create_sale(
                    db,
                    org_id=org.id,
                    data=SaleCreate(
                        lines=[SaleLineCreate(product_id=uuid.UUID(item["id"]), quantity=1)],
                        payment_method="cash",
                        amount_tendered=Decimal("100"),
                    ),
                    cashier_id=cashier.id,
                )
                return "sold"
            except InsufficientStockError:
                return "short"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(work, range(8)))

    assert outcomes.count("refunded") == 4
    sold = outcomes.count("sold")
    with SessionLocal() as db:
        assert db.get(Product, uuid.UUID(item["id"])).stock_on_hand == 2 + 4 - sold
        balances = db.scalars(
            select(StockMovement.balance_after)
            .where(StockMovement.product_id == uuid.UUID(item["id"]))
            .order_by(StockMovement.created_at, StockMovement.id)
        ).all()
    assert min(balances) >= 0


def test_the_database_refuses_refunded_quantities_above_what_was_sold(client, headers, receipt):
    line_id = uuid.UUID(receipt["sale"]["lines"][0]["id"])
    with SessionLocal() as db, pytest.raises(IntegrityError):
        db.execute(update(SaleLine).where(SaleLine.id == line_id).values(quantity_refunded=4))
        db.commit()


# ── Finding receipts ────────────────────────────────────────────────────────


def test_sales_list_shows_refunds_and_finds_a_receipt_by_number(client, headers, make_product):
    item = make_product(price="10.00", initial_stock=10)
    first = sell(client, headers, [{"product_id": item["id"], "quantity": 2}]).json()
    sell(client, headers, [{"product_id": item["id"], "quantity": 1}])
    refund(client, headers, first, [(0, 1)])

    for query in ("S-000001", "s000001", "1", " 000001 "):
        page = client.get("/api/v1/sales", params={"receipt": query}, headers=headers).json()
        assert [s["receipt_code"] for s in page["items"]] == ["S-000001"], query
        assert page["items"][0]["refunded_total"] == "10.00"
        assert page["items"][0]["refund_status"] == "partial"

    everything = client.get("/api/v1/sales", headers=headers).json()
    assert [s["refund_status"] for s in everything["items"]] == ["none", "partial"]

    bad = client.get("/api/v1/sales", params={"receipt": "abc"}, headers=headers)
    assert bad.status_code == 422

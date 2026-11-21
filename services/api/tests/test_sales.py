import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy import func, select

from app.core.errors import InsufficientStockError
from app.db.session import SessionLocal
from app.models import Product, Role, Sale, StockMovement
from app.schemas.sale import SaleCreate, SaleLineCreate
from app.services.sales import create_sale
from tests.conftest import auth_headers, make_member


def sell(client, headers, lines, *, cash="1000.00", key=None, **extra):
    body = {"lines": lines, "payment_method": "cash", "amount_tendered": cash} | extra
    hdrs = headers | ({"Idempotency-Key": key} if key else {})
    return client.post("/api/v1/sales", json=body, headers=hdrs)


def stock(client, headers, product_id):
    return client.get(f"/api/v1/products/{product_id}", headers=headers).json()["stock_on_hand"]


def test_cash_sale_totals_change_and_stock(client, headers, make_product):
    noodles = make_product(name="Pancit Canton", price="16.00", cost="13.50", initial_stock=10)
    coke = make_product(name="Coke 1.5L", price="80.00", cost="68.00", initial_stock=5)

    response = sell(
        client,
        headers,
        [{"product_id": noodles["id"], "quantity": 3}, {"product_id": coke["id"], "quantity": 1}],
        cash="200.00",
    )

    assert response.status_code == 201
    sale = response.json()
    assert sale["total"] == "128.00"  # 3 x 16 + 80
    assert sale["change_due"] == "72.00"
    assert sale["receipt_code"] == "S-000001"
    assert sale["item_count"] == 4
    assert [line["product_name"] for line in sale["lines"]] == ["Pancit Canton", "Coke 1.5L"]
    assert stock(client, headers, noodles["id"]) == 7
    assert stock(client, headers, coke["id"]) == 4


def test_prices_come_from_the_database_not_the_client(client, headers, make_product):
    product = make_product(price="25.00", initial_stock=5)
    response = sell(
        client, headers, [{"product_id": product["id"], "quantity": 1, "unit_price": "0.01"}]
    )
    assert response.json()["total"] == "25.00"


def test_scanning_the_same_item_twice_makes_one_line(client, headers, make_product):
    product = make_product(price="10.00", initial_stock=10)
    lines = [{"product_id": product["id"], "quantity": 1}] * 3
    sale = sell(client, headers, lines).json()
    assert len(sale["lines"]) == 1
    assert sale["lines"][0]["quantity"] == 3
    assert stock(client, headers, product["id"]) == 7


def test_short_stock_on_one_item_records_nothing(client, headers, make_product):
    plenty = make_product(initial_stock=50)
    scarce = make_product(name="Last one", initial_stock=1)

    response = sell(
        client,
        headers,
        [{"product_id": plenty["id"], "quantity": 2}, {"product_id": scarce["id"], "quantity": 2}],
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "insufficient_stock"
    assert body["fields"] == {scarce["id"]: "Only 1 left"}
    assert stock(client, headers, plenty["id"]) == 50  # rolled back entirely
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Sale)) == 0


def test_cash_must_cover_the_total(client, headers, make_product):
    product = make_product(price="50.00", initial_stock=5)
    response = sell(client, headers, [{"product_id": product["id"], "quantity": 2}], cash="99.99")
    assert response.status_code == 422
    assert "amount_tendered" in response.json()["error"]["fields"]
    assert stock(client, headers, product["id"]) == 5


def test_e_wallet_needs_a_reference_and_has_no_change(client, headers, make_product):
    product = make_product(price="30.00", initial_stock=5)
    line = [{"product_id": product["id"], "quantity": 1}]
    missing = client.post(
        "/api/v1/sales", json={"lines": line, "payment_method": "e_wallet"}, headers=headers
    )
    assert missing.status_code == 422

    ok = client.post(
        "/api/v1/sales",
        json={"lines": line, "payment_method": "e_wallet", "payment_reference": "GC-123456"},
        headers=headers,
    )
    assert ok.status_code == 201
    assert ok.json()["change_due"] is None
    assert ok.json()["payment_reference"] == "GC-123456"


def test_empty_cart_and_archived_products_are_refused(client, headers, make_product):
    assert sell(client, headers, []).status_code == 422
    product = make_product(initial_stock=5)
    client.delete(f"/api/v1/products/{product['id']}", headers=headers)
    assert sell(client, headers, [{"product_id": product["id"], "quantity": 1}]).status_code == 409


def test_retried_checkout_records_once(client, headers, make_product):
    product = make_product(initial_stock=10)
    line = [{"product_id": product["id"], "quantity": 2}]
    first = sell(client, headers, line, key="checkout-1")
    retry = sell(client, headers, line, key="checkout-1")
    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json()["id"] == first.json()["id"]
    assert stock(client, headers, product["id"]) == 8


def test_receipt_numbers_are_sequential_per_store(client, headers, other_headers, make_product):
    product = make_product(initial_stock=10)
    codes = [
        sell(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()["receipt_code"]
        for _ in range(3)
    ]
    assert codes == ["S-000001", "S-000002", "S-000003"]

    other_product = client.post(
        "/api/v1/products",
        json={"name": "B", "sku": "B", "price": "1", "initial_stock": 5},
        headers=other_headers,
    ).json()
    other = sell(client, other_headers, [{"product_id": other_product["id"], "quantity": 1}])
    assert other.json()["receipt_code"] == "S-000001"  # each store starts its own sequence


def test_sale_movements_link_to_the_receipt_and_cashier(client, org, make_product):
    product = make_product(initial_stock=5)
    cashier = auth_headers(org, Role.CASHIER)
    sale = sell(client, cashier, [{"product_id": product["id"], "quantity": 2}]).json()
    me = client.get("/api/v1/auth/me", headers=cashier).json()

    with SessionLocal() as db:
        movement = db.scalar(select(StockMovement).where(StockMovement.reason == "sale"))
        assert str(movement.sale_id) == sale["id"]
        assert str(movement.created_by_user_id) == me["user"]["id"]
        assert movement.note == "Receipt S-000001"
    assert sale["cashier_name"] == me["user"]["full_name"]


def test_cashiers_see_only_their_own_sales(client, org, headers, make_product):
    product = make_product(initial_stock=10)
    alice = auth_headers(org, Role.CASHIER)
    bob = auth_headers(org, Role.CASHIER)
    alice_sale = sell(client, alice, [{"product_id": product["id"], "quantity": 1}]).json()
    sell(client, bob, [{"product_id": product["id"], "quantity": 1}])

    assert client.get("/api/v1/sales", headers=alice).json()["total"] == 1
    assert client.get("/api/v1/sales", headers=headers).json()["total"] == 2  # owner sees all
    assert client.get(f"/api/v1/sales/{alice_sale['id']}", headers=bob).status_code == 404


def test_other_stores_cannot_sell_or_read_your_products(
    client, headers, other_headers, make_product
):
    product = make_product(initial_stock=5)
    response = sell(client, other_headers, [{"product_id": product["id"], "quantity": 1}])
    assert response.status_code == 404
    sale = sell(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    assert client.get(f"/api/v1/sales/{sale['id']}", headers=other_headers).status_code == 404


def test_lookup_by_barcode_or_sku(client, headers, make_product):
    product = make_product(sku="NDL-001", barcode="2000000000015")
    by_barcode = client.get(
        "/api/v1/products/lookup", params={"code": "2000000000015"}, headers=headers
    )
    by_sku = client.get("/api/v1/products/lookup", params={"code": "ndl-001"}, headers=headers)
    assert by_barcode.json()["id"] == by_sku.json()["id"] == product["id"]
    missing = client.get("/api/v1/products/lookup", params={"code": "nope"}, headers=headers)
    assert missing.status_code == 404


def test_concurrent_checkouts_never_oversell(org, make_product):
    """8 registers each try to sell 1 of the last 3 units, while also buying a shared item.

    Every checkout locks both products in the same order, so there are no deadlocks, exactly
    3 sales succeed, and receipt numbers stay unique."""
    scarce = make_product(initial_stock=3)
    shared = make_product(initial_stock=100)
    cashier = make_member(org, Role.CASHIER)
    lines = [
        SaleLineCreate(product_id=uuid.UUID(shared["id"]), quantity=1),
        SaleLineCreate(product_id=uuid.UUID(scarce["id"]), quantity=1),
    ]

    def checkout(i: int) -> str:
        data = SaleCreate(
            lines=lines if i % 2 else list(reversed(lines)),  # different cart orders
            payment_method="cash",
            amount_tendered=Decimal("1000"),
        )
        with SessionLocal() as db:
            try:
                create_sale(db, org_id=org.id, data=data, cashier_id=cashier.id)
                return "sold"
            except InsufficientStockError:
                return "short"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(checkout, range(8)))

    assert results.count("sold") == 3
    with SessionLocal() as db:
        assert db.get(Product, uuid.UUID(scarce["id"])).stock_on_hand == 0
        assert db.get(Product, uuid.UUID(shared["id"])).stock_on_hand == 97
        numbers = sorted(db.scalars(select(Sale.receipt_number)))
        assert numbers == [1, 2, 3]

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.core.errors import InsufficientStockError
from app.db.session import SessionLocal
from app.models import MovementReason, Product, StockMovement
from app.services.inventory import apply_stock_change


def adjust(client, headers, product_id, quantity_change, reason, key=None):
    extra = {"Idempotency-Key": key} if key else {}
    return client.post(
        f"/api/v1/products/{product_id}/stock-adjustments",
        json={"quantity_change": quantity_change, "reason": reason},
        headers=headers | extra,
    )


def stock_of(client, headers, product_id) -> int:
    return client.get(f"/api/v1/products/{product_id}", headers=headers).json()["stock_on_hand"]


def test_purchase_adds_and_damage_removes(client, headers, make_product):
    product = make_product(initial_stock=10)

    response = adjust(client, headers, product["id"], 24, "purchase")
    assert response.status_code == 201
    assert response.json()["balance_after"] == 34

    response = adjust(client, headers, product["id"], -4, "damage")
    assert response.json()["balance_after"] == 30
    assert stock_of(client, headers, product["id"]) == 30


def test_reason_must_match_direction(client, headers, make_product):
    product = make_product()
    assert adjust(client, headers, product["id"], -5, "purchase").status_code == 422
    assert adjust(client, headers, product["id"], 5, "damage").status_code == 422
    assert adjust(client, headers, product["id"], 0, "adjustment").status_code == 422
    assert adjust(client, headers, product["id"], 5, "initial").status_code == 422


def test_cannot_remove_more_than_on_hand(client, headers, make_product):
    product = make_product(initial_stock=3)

    response = adjust(client, headers, product["id"], -4, "sale")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    assert stock_of(client, headers, product["id"]) == 3  # nothing changed


def test_retried_request_with_same_key_applies_once(client, headers, make_product):
    product = make_product(initial_stock=10)

    first = adjust(client, headers, product["id"], -2, "sale", key="sale-123")
    retry = adjust(client, headers, product["id"], -2, "sale", key="sale-123")

    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert stock_of(client, headers, product["id"]) == 8


def test_blank_idempotency_key_is_ignored(client, headers, make_product):
    product = make_product(initial_stock=10)
    first = adjust(client, headers, product["id"], -1, "sale", key=" ")
    second = adjust(client, headers, product["id"], -1, "sale", key=" ")
    assert (first.status_code, second.status_code) == (201, 201)
    assert stock_of(client, headers, product["id"]) == 8


def test_archived_product_stock_is_frozen(client, headers, make_product):
    product = make_product()
    client.delete(f"/api/v1/products/{product['id']}", headers=headers)
    assert adjust(client, headers, product["id"], 1, "adjustment").status_code == 409


def test_concurrent_sales_never_oversell(org, client, headers, make_product):
    """10 cashiers try to sell 1 unit each at the same moment, but only 5 are in stock."""
    product = make_product(initial_stock=5)
    product_id = uuid.UUID(product["id"])

    def sell_one(_: int) -> str:
        with SessionLocal() as db:
            try:
                apply_stock_change(
                    db,
                    org_id=org.id,
                    product_id=product_id,
                    quantity_change=-1,
                    reason=MovementReason.SALE,
                )
                return "sold"
            except InsufficientStockError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(sell_one, range(10)))

    assert results.count("sold") == 5
    assert results.count("rejected") == 5
    with SessionLocal() as db:
        assert db.get(Product, product_id).stock_on_hand == 0
        ledger_total = db.scalar(
            select(func.sum(StockMovement.quantity_change)).where(
                StockMovement.product_id == product_id
            )
        )
        assert ledger_total == 0  # the ledger and the cached balance agree


def test_concurrent_retries_with_same_key_apply_once(org, make_product):
    product = make_product(initial_stock=10)
    product_id = uuid.UUID(product["id"])

    def sell(_: int) -> bool:
        with SessionLocal() as db:
            _, created = apply_stock_change(
                db,
                org_id=org.id,
                product_id=product_id,
                quantity_change=-1,
                reason=MovementReason.SALE,
                idempotency_key="same-key",
            )
            return created

    with ThreadPoolExecutor(max_workers=8) as pool:
        created_flags = list(pool.map(sell, range(8)))

    assert created_flags.count(True) == 1
    with SessionLocal() as db:
        assert db.get(Product, product_id).stock_on_hand == 9


def test_movement_history_is_newest_first(client, headers, make_product):
    product = make_product(initial_stock=10)
    adjust(client, headers, product["id"], 5, "purchase")
    adjust(client, headers, product["id"], -1, "sale")

    items = client.get(f"/api/v1/products/{product['id']}/movements", headers=headers).json()[
        "items"
    ]
    assert [m["reason"] for m in items] == ["sale", "purchase", "initial"]
    assert [m["balance_after"] for m in items] == [14, 15, 10]

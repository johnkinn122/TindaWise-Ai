import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import MovementReason, Organization, Role, StockMovement
from app.schemas.purchase_order import ReceiveInput, ReceiveLineInput
from app.services import purchase_orders as service
from tests.conftest import auth_headers, make_member

URL = "/api/v1/purchase-orders"


def supplier(client, headers, name="Puregold Wholesale"):
    response = client.post("/api/v1/suppliers", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def draft(client, headers, lines, supplier_id=None, key=None):
    body = {"lines": lines} | ({"supplier_id": supplier_id} if supplier_id else {})
    hdrs = headers | ({"Idempotency-Key": key} if key else {})
    return client.post(URL, json=body, headers=hdrs)


def approved_order(client, headers, lines):
    """Owner's headers: a draft with a supplier, approved."""
    sup = supplier(client, headers, name=f"Supplier {uuid.uuid4().hex[:6]}")
    po = draft(client, headers, lines, supplier_id=sup["id"]).json()
    response = client.post(f"{URL}/{po['id']}/approve", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def receive(client, headers, po, quantities, key=None):
    lines = [
        {"line_id": line["id"], "quantity": q}
        for line, q in zip(po["lines"], quantities, strict=True)
    ]
    hdrs = headers | ({"Idempotency-Key": key} if key else {})
    return client.post(f"{URL}/{po['id']}/receive", json={"lines": lines}, headers=hdrs)


def product(client, headers, product_id):
    return client.get(f"/api/v1/products/{product_id}", headers=headers).json()


# ── Drafts ──────────────────────────────────────────────────────────────────


def test_draft_uses_product_costs_and_numbers_per_store(client, headers, make_product):
    coke = make_product(name="Coke 1.5L", cost="68.00")
    soap = make_product(name="Safeguard", cost="38.00")

    first = draft(
        client,
        headers,
        [
            {"product_id": coke["id"], "quantity": 24},
            {"product_id": soap["id"], "quantity": 12, "unit_cost": "36.50"},
        ],
    )
    assert first.status_code == 201, first.text
    po = first.json()
    assert po["code"] == "PO-000001"
    assert po["status"] == "draft"
    assert po["supplier"] is None
    assert [
        (line["product_name"], line["unit_cost"], line["line_total"]) for line in po["lines"]
    ] == [
        ("Coke 1.5L", "68.00", "1632.00"),
        ("Safeguard", "36.50", "438.00"),
    ]
    assert po["total"] == "2070.00"
    assert po["history"][0]["action"] == "created"

    second = draft(client, headers, [{"product_id": coke["id"], "quantity": 1}]).json()
    assert second["code"] == "PO-000002"


def test_draft_rejects_repeated_archived_and_foreign_products(
    client, headers, other_headers, make_product
):
    item = make_product()
    repeated = draft(
        client,
        headers,
        [{"product_id": item["id"], "quantity": 1}, {"product_id": item["id"], "quantity": 2}],
    )
    assert repeated.status_code == 422

    archived = make_product(name="Old stock")
    client.delete(f"/api/v1/products/{archived['id']}", headers=headers)
    assert (
        draft(client, headers, [{"product_id": archived["id"], "quantity": 1}]).status_code == 409
    )

    theirs = client.post(
        "/api/v1/products",
        json={"name": "Theirs", "sku": "T-1", "price": "5.00"},
        headers=other_headers,
    ).json()
    assert draft(client, headers, [{"product_id": theirs["id"], "quantity": 1}]).status_code == 404
    their_supplier = supplier(client, other_headers)
    assert (
        draft(
            client, headers, [{"product_id": item["id"], "quantity": 1}], their_supplier["id"]
        ).status_code
        == 404
    )


def test_editing_a_draft_replaces_its_lines(client, headers, make_product):
    a, b = make_product(name="A", cost="10.00"), make_product(name="B", cost="20.00")
    po = draft(client, headers, [{"product_id": a["id"], "quantity": 5}]).json()
    sup = supplier(client, headers)

    # Same product kept and moved to a new position: unique (order, product) must not trip.
    edited = client.patch(
        f"{URL}/{po['id']}",
        json={
            "supplier_id": sup["id"],
            "notes": "Deliver before payday",
            "lines": [
                {"product_id": b["id"], "quantity": 2},
                {"product_id": a["id"], "quantity": 7},
            ],
        },
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert [(line["product_name"], line["quantity_ordered"]) for line in body["lines"]] == [
        ("B", 2),
        ("A", 7),
    ]
    assert body["total"] == "110.00"
    assert body["supplier"]["name"] == "Puregold Wholesale"
    assert body["notes"] == "Deliver before payday"


def test_creating_with_the_same_key_twice_makes_one_draft(client, headers, make_product):
    item = make_product()
    first = draft(client, headers, [{"product_id": item["id"], "quantity": 1}], key="po-abc")
    again = draft(client, headers, [{"product_id": item["id"], "quantity": 1}], key="po-abc")
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert client.get(URL, headers=headers).json()["total"] == 1


# ── Approval ────────────────────────────────────────────────────────────────


def test_only_the_owner_approves_and_a_supplier_is_required(client, org, headers, make_product):
    item = make_product()
    manager = auth_headers(org, Role.MANAGER)
    po = draft(client, manager, [{"product_id": item["id"], "quantity": 3}]).json()

    no_supplier = client.post(f"{URL}/{po['id']}/approve", headers=headers)
    assert no_supplier.status_code == 422
    assert no_supplier.json()["error"]["fields"] == {"supplier_id": "Choose a supplier"}

    sup = supplier(client, manager)
    client.patch(f"{URL}/{po['id']}", json={"supplier_id": sup["id"]}, headers=manager)
    assert client.post(f"{URL}/{po['id']}/approve", headers=manager).status_code == 403

    approved = client.post(f"{URL}/{po['id']}/approve", headers=headers).json()
    assert approved["status"] == "approved"
    assert [event["action"] for event in approved["history"]] == ["created", "approved"]
    assert approved["history"][0]["by"] == "Test manager"
    assert approved["history"][1]["by"] == "Test owner"

    locked = client.patch(f"{URL}/{po['id']}", json={"notes": "late change"}, headers=headers)
    assert locked.status_code == 409


def test_an_archived_supplier_cannot_be_approved(client, headers, make_product):
    item = make_product()
    sup = supplier(client, headers)
    po = draft(client, headers, [{"product_id": item["id"], "quantity": 1}], sup["id"]).json()
    client.delete(f"/api/v1/suppliers/{sup['id']}", headers=headers)
    assert client.post(f"{URL}/{po['id']}/approve", headers=headers).status_code == 409


# ── Receiving ───────────────────────────────────────────────────────────────


def test_partial_then_full_delivery_adds_stock_and_updates_cost(client, headers, make_product):
    coke = make_product(name="Coke", cost="60.00", initial_stock=2)
    soap = make_product(name="Soap", cost="30.00", initial_stock=0)
    po = approved_order(
        client,
        headers,
        [
            {"product_id": coke["id"], "quantity": 24, "unit_cost": "68.00"},
            {"product_id": soap["id"], "quantity": 12},
        ],
    )

    first = receive(client, headers, po, [18, 0])
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["status"] == "partially_received"
    assert [line["quantity_remaining"] for line in body["lines"]] == [6, 12]
    assert product(client, headers, coke["id"])["stock_on_hand"] == 20
    assert product(client, headers, coke["id"])["cost"] == "68.00"  # latest-cost rule
    assert product(client, headers, soap["id"])["cost"] == "30.00"  # nothing arrived yet

    movements = client.get(f"/api/v1/products/{coke['id']}/movements", headers=headers).json()
    latest = movements["items"][0]
    assert (latest["reason"], latest["quantity_change"], latest["balance_after"]) == (
        "purchase",
        18,
        20,
    )
    assert latest["note"] == f"Received on {po['code']}"

    done = receive(client, headers, body, [6, 12]).json()
    assert done["status"] == "received"
    assert [r["lines"][0]["quantity"] for r in done["receipts"]] == [18, 6]
    assert [event["action"] for event in done["history"]] == [
        "created",
        "approved",
        "received",
        "received",
    ]
    assert product(client, headers, soap["id"])["stock_on_hand"] == 12


def test_cannot_receive_more_than_ordered_or_before_approval(client, headers, make_product):
    item = make_product(initial_stock=0)
    sup = supplier(client, headers)
    po = draft(client, headers, [{"product_id": item["id"], "quantity": 5}], sup["id"]).json()
    assert receive(client, headers, po, [1]).status_code == 409  # still a draft

    client.post(f"{URL}/{po['id']}/approve", headers=headers)
    too_many = receive(client, headers, po, [6])
    assert too_many.status_code == 422
    assert too_many.json()["error"]["fields"] == {po["lines"][0]["id"]: "Only 5 left to receive"}
    assert receive(client, headers, po, [0]).status_code == 422  # nothing arrived
    assert product(client, headers, item["id"])["stock_on_hand"] == 0


def test_a_retried_delivery_is_applied_once(client, headers, make_product):
    item = make_product(initial_stock=0)
    po = approved_order(client, headers, [{"product_id": item["id"], "quantity": 10}])

    first = receive(client, headers, po, [4], key="dr-001")
    again = receive(client, headers, po, [4], key="dr-001")
    assert (first.status_code, again.status_code) == (201, 200)
    assert product(client, headers, item["id"])["stock_on_hand"] == 4
    assert len(again.json()["receipts"]) == 1


def test_concurrent_deliveries_never_receive_more_than_ordered(org, client, headers, make_product):
    item = make_product(initial_stock=0)
    po = approved_order(client, headers, [{"product_id": item["id"], "quantity": 10}])
    user = make_member(org, Role.MANAGER)
    line_id = uuid.UUID(po["lines"][0]["id"])

    def attempt(_: int) -> str:
        with SessionLocal() as db:
            try:
                service.receive(
                    db,
                    org_id=org.id,
                    po_id=uuid.UUID(po["id"]),
                    data=ReceiveInput(lines=[ReceiveLineInput(line_id=line_id, quantity=6)]),
                    user_id=user.id,
                )
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(attempt, range(4)))

    assert outcomes.count("ok") == 1  # 6 fits once into 10; the rest see "only 4 left"
    assert product(client, headers, item["id"])["stock_on_hand"] == 6
    with SessionLocal() as db:
        received = db.scalars(
            select(StockMovement).where(
                StockMovement.product_id == uuid.UUID(item["id"]),
                StockMovement.reason == MovementReason.PURCHASE.value,
            )
        ).all()
    assert sum(m.quantity_change for m in received) == 6


# ── Close and cancel ────────────────────────────────────────────────────────


def test_close_short_keeps_what_arrived(client, headers, make_product):
    item = make_product(initial_stock=0)
    po = approved_order(client, headers, [{"product_id": item["id"], "quantity": 10}])
    assert client.post(f"{URL}/{po['id']}/close", headers=headers).status_code == 409  # nothing yet

    receive(client, headers, po, [7])
    closed = client.post(f"{URL}/{po['id']}/close", headers=headers).json()
    assert closed["status"] == "closed"
    assert closed["history"][-1]["action"] == "closed"
    assert product(client, headers, item["id"])["stock_on_hand"] == 7
    assert receive(client, headers, closed, [3]).status_code == 409


def test_cancel_rules(client, org, headers, make_product):
    item = make_product(initial_stock=0)
    manager = auth_headers(org, Role.MANAGER)

    po = draft(client, manager, [{"product_id": item["id"], "quantity": 1}]).json()
    assert client.post(f"{URL}/{po['id']}/cancel", headers=manager).json()["status"] == "cancelled"

    approved = approved_order(client, headers, [{"product_id": item["id"], "quantity": 2}])
    assert client.post(f"{URL}/{approved['id']}/cancel", headers=manager).status_code == 403
    assert client.post(f"{URL}/{approved['id']}/cancel", headers=headers).status_code == 200

    partly = approved_order(client, headers, [{"product_id": item["id"], "quantity": 2}])
    receive(client, headers, partly, [1])
    assert client.post(f"{URL}/{partly['id']}/cancel", headers=headers).status_code == 409


# ── From the Overview, listing, access ──────────────────────────────────────


def test_draft_from_reorder_suggestions(client, headers, make_product):
    make_product(name="Bare shelf", initial_stock=0, reorder_level=5, cost="8.00")
    make_product(name="Plenty", initial_stock=50, reorder_level=5)

    response = client.post(f"{URL}/from-reorder", headers=headers | {"Idempotency-Key": "ov-1"})
    assert response.status_code == 201, response.text
    po = response.json()
    assert [
        (line["product_name"], line["quantity_ordered"], line["unit_cost"]) for line in po["lines"]
    ] == [("Bare shelf", 10, "8.00")]
    assert po["supplier"] is None
    replay = client.post(f"{URL}/from-reorder", headers=headers | {"Idempotency-Key": "ov-1"})
    assert (replay.status_code, replay.json()["id"]) == (200, po["id"])


def test_nothing_to_reorder_is_a_clear_conflict(client, headers, make_product):
    make_product(initial_stock=50, reorder_level=5)
    response = client.post(f"{URL}/from-reorder", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Nothing needs reordering right now."


def test_list_filters_by_status(client, headers, make_product):
    item = make_product()
    draft(client, headers, [{"product_id": item["id"], "quantity": 1}])
    approved_order(client, headers, [{"product_id": item["id"], "quantity": 1}])

    drafts = client.get(URL, params={"status": "draft"}, headers=headers).json()
    assert [po["status"] for po in drafts["items"]] == ["draft"]
    both = client.get(
        URL, params=[("status", "draft"), ("status", "approved")], headers=headers
    ).json()
    assert both["total"] == 2
    assert both["items"][0]["line_count"] == 1


def test_cashiers_have_no_access_and_stores_are_isolated(
    client, org, headers, other_headers, make_product
):
    item = make_product()
    po = draft(client, headers, [{"product_id": item["id"], "quantity": 1}]).json()
    cashier = auth_headers(org, Role.CASHIER)
    assert client.get(URL, headers=cashier).status_code == 403
    assert client.get(f"{URL}/{po['id']}", headers=cashier).status_code == 403
    assert client.post(f"{URL}/from-reorder", headers=cashier).status_code == 403

    assert client.get(f"{URL}/{po['id']}", headers=other_headers).status_code == 404
    assert client.post(f"{URL}/{po['id']}/approve", headers=other_headers).status_code == 404
    with SessionLocal() as db:
        assert db.get(Organization, org.id).last_po_number == 1

"""The append-only audit trail: what's recorded, when, and who can read it."""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal
from app.models import AuditEvent, Role
from app.schemas.auth import LoginRequest
from app.services.auth import login
from tests.conftest import TEST_PASSWORD, auth_headers, make_member
from tests.test_purchase_orders import URL as PO_URL
from tests.test_purchase_orders import approved_order, draft, receive, supplier
from tests.test_refunds import refund
from tests.test_reports import sell

URL = "/api/v1/audit-events"


def events(org_id) -> list[AuditEvent]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == org_id)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        )


def only(org_id, action: str) -> AuditEvent:
    found = [e for e in events(org_id) if e.action == action]
    assert len(found) == 1, [e.action for e in events(org_id)]
    return found[0]


def me(client, headers) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["user"]["id"])


# ── What is recorded ────────────────────────────────────────────────────────


def test_store_settings_change(client, org, headers):
    client.patch(
        "/api/v1/store", json={"name": "Renamed", "default_lead_time_days": 5}, headers=headers
    )
    event = only(org.id, "store.updated")
    assert event.actor_user_id == me(client, headers)
    assert (event.entity_type, event.entity_id) == ("store", org.id)
    assert event.summary == "Changed store settings: name, default delivery time"
    assert event.details == {
        "changes": {"name": ["Test Store A", "Renamed"], "default_lead_time_days": [3, 5]}
    }


def test_saving_unchanged_settings_records_nothing(client, org, headers):
    client.patch("/api/v1/store", json={"name": "Test Store A", "timezone": "Asia/Manila"},
                 headers=headers)  # fmt: skip
    assert events(org.id) == []


def test_member_added(client, org, headers):
    client.post(
        "/api/v1/members",
        json={"full_name": "Ana Cruz", "email": "ana@example.com", "role": "cashier",
              "temporary_password": "temporary-pass-1"},
        headers=headers,
    )  # fmt: skip
    event = only(org.id, "member.added")
    assert event.summary == "Added Ana Cruz (ana@example.com) as cashier"
    assert event.details == {"email": "ana@example.com", "role": "cashier"}


def test_refund_recorded_once_even_when_retried(client, org, headers, make_product):
    product = make_product(price="25.00", initial_stock=10)
    sale = sell(client, headers, [(product, 3)])
    assert refund(client, headers, sale, [(0, 2, False)], key="r-1").status_code == 201
    assert refund(client, headers, sale, [(0, 2, False)], key="r-1").status_code == 200  # replay

    event = only(org.id, "refund.created")
    assert event.summary == "Refunded ₱50.00 on S-000001 (R-000001): 2 units, customer return"
    assert event.details | {"sale_id": None} == {
        "refund_code": "R-000001", "receipt_code": "S-000001", "sale_id": None,
        "total": "50.00", "units": 2, "restocked_units": 0, "reason": "customer_return",
    }  # fmt: skip


def test_a_refused_refund_records_nothing(client, org, headers, make_product):
    product = make_product(initial_stock=10)
    sale = sell(client, headers, [(product, 1)])
    assert refund(client, headers, sale, [(0, 5)]).status_code == 409  # more than was sold
    assert events(org.id) == []


def test_purchase_order_approve_close_and_cancel(client, org, headers, make_product):
    product = make_product(name="Soap", cost="10.00")
    po = approved_order(client, headers, [{"product_id": product["id"], "quantity": 6}])
    approved = only(org.id, "purchase_order.approved")
    assert approved.summary.startswith(f"Approved {po['code']} for ₱60.00 from Supplier ")
    assert (approved.entity_type, str(approved.entity_id)) == ("purchase_order", po["id"])

    assert receive(client, headers, po, [4]).status_code == 201
    assert client.post(f"{PO_URL}/{po['id']}/close", headers=headers).status_code == 200
    closed = only(org.id, "purchase_order.closed")
    assert closed.summary == f"Closed {po['code']} short: 4 of 6 units received"

    other = draft(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    assert client.post(f"{PO_URL}/{other['id']}/cancel", headers=headers).status_code == 200
    cancelled = only(org.id, "purchase_order.cancelled")
    assert cancelled.summary == f"Cancelled {other['code']} (draft)"
    assert cancelled.details == {"code": other["code"], "status_before": "draft"}


def test_approving_without_a_supplier_records_nothing(client, org, headers, make_product):
    product = make_product()
    po = draft(client, headers, [{"product_id": product["id"], "quantity": 1}]).json()
    assert client.post(f"{PO_URL}/{po['id']}/approve", headers=headers).status_code == 422
    assert events(org.id) == []


def test_price_and_cost_changes_but_not_other_edits(client, org, headers, make_product):
    product = make_product(name="Coke 1.5L", sku="BEV-1", price="80.00", cost="68.00")
    url = f"/api/v1/products/{product['id']}"
    client.patch(url, json={"name": "Coca-Cola 1.5L", "reorder_level": 9}, headers=headers)
    client.patch(url, json={"price": "80.00"}, headers=headers)  # same price: not a change
    assert events(org.id) == []

    client.patch(url, json={"price": "82.50", "cost": "70.00"}, headers=headers)
    event = only(org.id, "product.price_changed")
    assert event.summary == "Changed Coca-Cola 1.5L: price ₱80.00 → ₱82.50; cost ₱68.00 → ₱70.00"
    assert event.details == {
        "sku": "BEV-1", "changes": {"price": ["80.00", "82.50"], "cost": ["68.00", "70.00"]},
    }  # fmt: skip


def test_archive_recorded_once(client, org, headers, make_product):
    product = make_product(name="Old item", sku="OLD-1", initial_stock=4)
    url = f"/api/v1/products/{product['id']}"
    assert client.delete(url, headers=headers).status_code == 204
    assert client.delete(url, headers=headers).status_code in (204, 404)
    event = only(org.id, "product.archived")
    assert event.summary == "Archived Old item (OLD-1)"
    assert event.details == {"sku": "OLD-1", "stock_on_hand": 4}


def test_routine_work_is_not_logged(client, org, headers, make_product):
    """Sales and stock changes have their own records (receipts, the stock ledger)."""
    product = make_product(initial_stock=5)
    sell(client, headers, [(product, 1)])
    client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"quantity_change": 3, "reason": "purchase"},
        headers=headers,
    )
    supplier(client, headers)
    assert events(org.id) == []


# ── Append-only ─────────────────────────────────────────────────────────────


def test_the_database_refuses_to_edit_or_delete_audit_events(client, org, headers):
    client.patch("/api/v1/store", json={"name": "Renamed"}, headers=headers)
    [event] = events(org.id)
    for statement in (
        update(AuditEvent).where(AuditEvent.id == event.id).values(summary="nothing happened"),
        delete(AuditEvent).where(AuditEvent.id == event.id),
    ):
        with SessionLocal() as db, pytest.raises(DBAPIError, match="append-only"):
            db.execute(statement)
            db.commit()
    with SessionLocal() as db:
        assert db.get(AuditEvent, event.id).summary == "Changed store settings: name"
        # Raw SQL is refused too: the rule lives in the database, not in the app.
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text("DELETE FROM audit_events"))


# ── Reading the log ─────────────────────────────────────────────────────────


def test_owner_reads_newest_first_with_names(client, org, headers):
    client.patch("/api/v1/store", json={"name": "First"}, headers=headers)
    client.patch("/api/v1/store", json={"name": "Second"}, headers=headers)
    body = client.get(URL, headers=headers).json()
    assert body["total"] == 2
    newest, older = body["items"]
    assert newest["details"]["changes"]["name"] == ["First", "Second"]
    assert older["details"]["changes"]["name"] == ["Test Store A", "First"]
    assert newest["actor_name"] == "Test owner"
    assert newest["action"] == "store.updated"


def test_filters_and_pages(client, org, headers, make_product):
    product = make_product(price="10.00")
    client.patch(f"/api/v1/products/{product['id']}", json={"price": "11.00"}, headers=headers)
    client.patch("/api/v1/store", json={"name": "A"}, headers=headers)
    client.patch("/api/v1/store", json={"name": "B"}, headers=headers)

    by_action = client.get(URL, params={"action": "store.updated"}, headers=headers).json()
    assert by_action["total"] == 2
    page = client.get(URL, params={"limit": 1, "offset": 1}, headers=headers).json()
    assert (page["total"], len(page["items"])) == (3, 1)
    owner = str(me(client, headers))
    assert client.get(URL, params={"actor_id": owner}, headers=headers).json()["total"] == 3
    nobody = str(uuid.uuid4())
    assert client.get(URL, params={"actor_id": nobody}, headers=headers).json()["total"] == 0
    assert client.get(URL, params={"action": "nope"}, headers=headers).status_code == 422


def test_date_range_uses_store_days(client, org, headers):
    client.patch("/api/v1/store", json={"name": "Renamed"}, headers=headers)
    [event] = events(org.id)
    # The trigger blocks UPDATE, so check the range against the event's real time instead.
    day = event.created_at.astimezone(ZoneInfo("Asia/Manila")).date()
    inside = client.get(URL, params={"start": str(day), "end": str(day)}, headers=headers).json()
    assert inside["total"] == 1
    before = client.get(URL, params={"end": "2020-01-01"}, headers=headers).json()
    assert before["total"] == 0
    bad = client.get(URL, params={"start": "2026-11-05", "end": "2026-11-01"}, headers=headers)
    assert bad.status_code == 422


def test_only_the_owner_reads_the_log(client, org):
    for role in (Role.MANAGER, Role.CASHIER):
        assert client.get(URL, headers=auth_headers(org, role)).status_code == 403
    assert client.get(URL).status_code == 401


def test_each_store_sees_only_its_own_events(client, org, headers, other_headers):
    client.patch("/api/v1/store", json={"name": "B renamed"}, headers=other_headers)
    assert client.get(URL, headers=headers).json()["total"] == 0
    assert client.get(URL, headers=other_headers).json()["total"] == 1


def test_a_managers_actions_are_attributed_to_the_manager(client, org, make_product):
    manager_user = make_member(org, Role.MANAGER)
    with SessionLocal() as db:
        _, token = login(db, LoginRequest(email=manager_user.email, password=TEST_PASSWORD))
    manager = {"Authorization": f"Bearer {token}"}
    product = client.post(
        "/api/v1/products",
        json={"name": "Item", "sku": "M-1", "price": "5.00"},
        headers=manager,
    ).json()
    client.patch(f"/api/v1/products/{product['id']}", json={"price": "6.00"}, headers=manager)
    event = only(org.id, "product.price_changed")
    assert event.actor_user_id == manager_user.id
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(AuditEvent))
    assert count == 1
    assert event.created_at <= datetime.now(UTC)

"""Store settings: GET/PATCH /api/v1/store."""

from datetime import UTC, datetime

from app.db.session import SessionLocal
from app.models import Organization, Role
from app.services.overview import build_overview
from tests.conftest import auth_headers

URL = "/api/v1/store"


def test_owner_reads_the_store_settings(client, org, headers):
    body = client.get(URL, headers=headers).json()
    assert body | {"updated_at": None} == {
        "id": str(org.id),
        "name": "Test Store A",
        "currency": "PHP",
        "timezone": "Asia/Manila",
        "default_lead_time_days": 3,
        "updated_at": None,
    }


def test_owner_changes_only_what_is_sent(client, headers):
    changed = client.patch(URL, json={"name": "  Aling Nena's Store  "}, headers=headers).json()
    assert changed["name"] == "Aling Nena's Store"  # trimmed
    assert (changed["timezone"], changed["default_lead_time_days"]) == ("Asia/Manila", 3)

    changed = client.patch(
        URL, json={"timezone": "Asia/Singapore", "default_lead_time_days": 0}, headers=headers
    ).json()
    assert (changed["name"], changed["timezone"], changed["default_lead_time_days"]) == (
        "Aling Nena's Store",
        "Asia/Singapore",
        0,
    )
    # The new name is what the app shows everywhere (top bar, receipts).
    assert client.get("/api/v1/auth/me", headers=headers).json()["organization"]["name"] == (
        "Aling Nena's Store"
    )


def test_nulls_and_an_empty_body_change_nothing(client, headers):
    before = client.get(URL, headers=headers).json()
    assert client.patch(URL, json={}, headers=headers).json()["name"] == before["name"]
    after = client.patch(URL, json={"name": None, "timezone": None}, headers=headers).json()
    assert (after["name"], after["timezone"]) == (before["name"], before["timezone"])


def test_invalid_values_are_field_errors(client, headers):
    for body, field in (
        ({"name": "   "}, "name"),
        ({"name": "x" * 161}, "name"),
        ({"timezone": "Manila"}, "timezone"),
        ({"timezone": "Factory"}, "timezone"),
        ({"default_lead_time_days": 61}, "default_lead_time_days"),
        ({"default_lead_time_days": -1}, "default_lead_time_days"),
    ):
        response = client.patch(URL, json=body, headers=headers)
        assert response.status_code == 422, body
        assert field in response.json()["error"]["fields"], body
    message = client.patch(URL, json={"timezone": "Manila"}, headers=headers).json()
    assert "Asia/Manila" in message["error"]["fields"]["timezone"]


def test_currency_cannot_be_changed(client, headers):
    changed = client.patch(URL, json={"currency": "USD", "name": "Kept"}, headers=headers).json()
    assert (changed["currency"], changed["name"]) == ("PHP", "Kept")


def test_managers_can_read_but_not_change(client, org):
    manager = auth_headers(org, Role.MANAGER)
    assert client.get(URL, headers=manager).status_code == 200
    response = client.patch(URL, json={"name": "Mine now"}, headers=manager)
    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.get(Organization, org.id).name == "Test Store A"


def test_cashiers_and_signed_out_visitors_are_refused(client, org):
    cashier = auth_headers(org, Role.CASHIER)
    assert client.get(URL, headers=cashier).status_code == 403
    assert client.patch(URL, json={"name": "x"}, headers=cashier).status_code == 403
    assert client.get(URL).status_code == 401
    assert client.patch(URL, json={"name": "x"}).status_code == 401


def test_each_owner_changes_only_their_own_store(client, org, other_org, headers, other_headers):
    client.patch(URL, json={"name": "Store B renamed"}, headers=other_headers)
    with SessionLocal() as db:
        assert db.get(Organization, org.id).name == "Test Store A"
        assert db.get(Organization, other_org.id).name == "Store B renamed"
    assert client.get(URL, headers=headers).json()["name"] == "Test Store A"


def test_the_time_zone_decides_where_today_starts(client, org, headers):
    # 23:30 UTC on 21 Nov is 22 Nov in Manila (UTC+8) but still 21 Nov in Honolulu (UTC-10).
    now = datetime(2026, 11, 21, 23, 30, tzinfo=UTC)

    def today():
        with SessionLocal() as db:
            store = db.get(Organization, org.id)
            return build_overview(db, store, cashier_id=None, include_costs=True, now=now)

    assert today().week[0].date.isoformat() == "2026-11-22"  # Manila: a Sunday starts the week
    client.patch(URL, json={"timezone": "Pacific/Honolulu"}, headers=headers)
    assert today().week[0].date.isoformat() == "2026-11-15"  # Honolulu: still Saturday the 21st


def test_the_default_delivery_time_feeds_reorder_suggestions(client, headers, make_product):
    make_product(name="Bare shelf", initial_stock=0, reorder_level=5)
    client.patch(URL, json={"default_lead_time_days": 6}, headers=headers)
    [line] = client.get("/api/v1/overview", headers=headers).json()["reorder"]["lines"]
    assert (line["lead_time_days"], line["lead_time_source"]) == (6, "store_default")

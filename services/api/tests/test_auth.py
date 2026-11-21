from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models import AuthSession, Role, StockMovement, User
from tests.conftest import TEST_PASSWORD, auth_headers, make_member

SIGNUP = {
    "full_name": "Nena Santos",
    "email": "Nena@Example.com",
    "password": "a-long-enough-password",
    "store_name": "Nena's Store",
}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_signup_creates_owner_store_and_session(client):
    response = client.post("/api/v1/auth/signup", json=SIGNUP)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "owner"
    assert body["organization"]["name"] == "Nena's Store"
    assert body["user"]["email"] == "nena@example.com"  # normalized
    assert "password" not in str(body).lower().replace("password_hash", "")

    me = client.get("/api/v1/auth/me", headers=bearer(body["token"]))
    assert me.status_code == 200
    assert me.json()["user"]["full_name"] == "Nena Santos"


def test_signup_rejects_short_password_and_duplicate_email(client):
    short = client.post("/api/v1/auth/signup", json=SIGNUP | {"password": "short"})
    assert short.status_code == 422
    assert "password" in short.json()["error"]["fields"]

    assert client.post("/api/v1/auth/signup", json=SIGNUP).status_code == 201
    again = client.post("/api/v1/auth/signup", json=SIGNUP | {"email": "NENA@example.com"})
    assert again.status_code == 409
    assert again.json()["error"]["fields"] == {"email": "Already has an account"}


def test_password_is_stored_hashed(client):
    client.post("/api/v1/auth/signup", json=SIGNUP)
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="nena@example.com").one()
        assert user.password_hash.startswith("$argon2id$")
        assert SIGNUP["password"] not in user.password_hash


def test_session_token_is_stored_hashed(client):
    token = client.post("/api/v1/auth/signup", json=SIGNUP).json()["token"]
    with SessionLocal() as db:
        hashes = [s.token_hash for s in db.query(AuthSession).all()]
    assert token not in hashes
    assert all(len(h) == 64 for h in hashes)


def test_login_success_and_uniform_failure_message(client, org):
    user = make_member(org, Role.MANAGER)
    ok = client.post(
        "/api/v1/auth/login", json={"email": user.email.upper(), "password": TEST_PASSWORD}
    )
    assert ok.status_code == 200
    assert ok.json()["role"] == "manager"

    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "not-the-password"}
    )
    unknown_email = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"}
    )
    # Same status and message, so the response doesn't reveal which emails have accounts.
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_deactivated_user_cannot_sign_in(client, org):
    user = make_member(org, Role.CASHIER)
    with SessionLocal() as db:
        db.get(User, user.id).is_active = False
        db.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 401


def test_logout_revokes_the_session(client, headers):
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_expired_session_is_refused(client, headers):
    with SessionLocal() as db:
        for session in db.query(AuthSession).all():
            session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    response = client.get("/api/v1/products", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize(
    "header",
    [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer made-up-token"},
        {"Authorization": "Basic abc"},
    ],
)
def test_requests_without_a_valid_session_are_refused(client, header):
    assert client.get("/api/v1/products", headers=header).status_code == 401


# ── Roles ───────────────────────────────────────────────────────────────────


def test_cashier_can_look_but_not_change(client, org, make_product):
    product = make_product()
    cashier = auth_headers(org, Role.CASHIER)
    url = f"/api/v1/products/{product['id']}"

    assert client.get("/api/v1/products", headers=cashier).status_code == 200
    assert client.get(url, headers=cashier).status_code == 200
    forbidden = [
        client.post(
            "/api/v1/products", json={"name": "x", "sku": "x", "price": "1"}, headers=cashier
        ),
        client.patch(url, json={"name": "x"}, headers=cashier),
        client.delete(url, headers=cashier),
        client.post(
            f"{url}/stock-adjustments",
            json={"quantity_change": 1, "reason": "adjustment"},
            headers=cashier,
        ),
        client.post("/api/v1/categories", json={"name": "x"}, headers=cashier),
        client.get("/api/v1/members", headers=cashier),
    ]
    assert [r.status_code for r in forbidden] == [403] * len(forbidden)
    assert forbidden[0].json()["error"]["code"] == "forbidden"


def test_manager_runs_inventory_but_not_the_team(client, org, make_product):
    product = make_product(initial_stock=5)
    manager = auth_headers(org, Role.MANAGER)
    adjust = client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"quantity_change": 3, "reason": "purchase"},
        headers=manager,
    )
    assert adjust.status_code == 201
    assert client.get("/api/v1/members", headers=manager).status_code == 403


def test_stock_changes_record_who_made_them(client, org, headers, make_product):
    product = make_product(initial_stock=5)
    client.post(
        f"/api/v1/products/{product['id']}/stock-adjustments",
        json={"quantity_change": -1, "reason": "damage"},
        headers=headers,
    )
    me = client.get("/api/v1/auth/me", headers=headers).json()
    with SessionLocal() as db:
        authors = {str(m.created_by_user_id) for m in db.query(StockMovement).all()}
    assert authors == {me["user"]["id"]}


# ── Team ────────────────────────────────────────────────────────────────────


def test_owner_adds_a_cashier_who_can_then_sign_in(client, headers):
    created = client.post(
        "/api/v1/members",
        json={
            "full_name": "Carlo Dizon",
            "email": "carlo@example.com",
            "role": "cashier",
            "temporary_password": "temporary-pass-1",
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["role"] == "cashier"

    members = client.get("/api/v1/members", headers=headers).json()
    assert {m["role"] for m in members} == {"owner", "cashier"}

    login = client.post(
        "/api/v1/auth/login", json={"email": "carlo@example.com", "password": "temporary-pass-1"}
    )
    assert login.status_code == 200
    assert login.json()["role"] == "cashier"


def test_owner_cannot_add_another_owner_or_an_existing_account(client, org, headers):
    as_owner = client.post(
        "/api/v1/members",
        json={
            "full_name": "X",
            "email": "x@example.com",
            "role": "owner",
            "temporary_password": "0123456789",
        },
        headers=headers,
    )
    assert as_owner.status_code == 422

    existing = make_member(org, Role.CASHIER, email="taken@example.com")
    duplicate = client.post(
        "/api/v1/members",
        json={
            "full_name": "Y",
            "email": existing.email,
            "role": "manager",
            "temporary_password": "0123456789",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409


def test_members_are_scoped_to_the_organization(client, headers, other_headers):
    client.post(
        "/api/v1/members",
        json={
            "full_name": "A",
            "email": "a@example.com",
            "role": "cashier",
            "temporary_password": "0123456789",
        },
        headers=headers,
    )
    other_members = client.get("/api/v1/members", headers=other_headers).json()
    assert [m["email"] for m in other_members if m["email"] == "a@example.com"] == []

"""The public demo: settings, sign-up off, and the guards on the seed and reset scripts."""

import pytest
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import AuditEvent, Organization, User
from scripts import reset_demo, seed, seed_sample_history


@pytest.fixture
def env(monkeypatch):
    """Set environment variables for one test; settings are re-read before and after."""

    def _set(**values: str) -> None:
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


def count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model)) or 0


# ── Settings ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("given", "used"),
    [
        ("postgresql://u:p@db.neon.tech/app?sslmode=require",
         "postgresql+psycopg://u:p@db.neon.tech/app?sslmode=require"),
        ("postgres://u:p@host:5432/app", "postgresql+psycopg://u:p@host:5432/app"),
        ("postgresql+psycopg://u:p@localhost/app", "postgresql+psycopg://u:p@localhost/app"),
    ],
)  # fmt: skip
def test_host_urls_use_the_installed_driver(given, used):
    assert Settings(database_url=given).database_url == used
    assert Settings(test_database_url=given).test_database_url == used


@pytest.mark.parametrize(
    ("environment", "demo", "allowed"),
    [("development", False, True), ("test", False, True), ("production", False, False),
     ("production", True, True)],
)  # fmt: skip
def test_sample_data_only_off_production_or_on_the_demo(environment, demo, allowed):
    assert Settings(environment=environment, demo_mode=demo).sample_data_allowed is allowed


# ── Sign-up ─────────────────────────────────────────────────────────────────

SIGNUP = {
    "full_name": "Visitor",
    "email": "visitor@example.com",
    "password": "a-long-enough-password",
    "store_name": "Visitor's Store",
}


def test_sign_up_is_off_on_the_demo_and_sign_in_still_works(env, client):
    seed.main()
    env(DEMO_MODE="true")
    response = client.post("/api/v1/auth/signup", json=SIGNUP)
    assert response.status_code == 403
    assert "public demo" in response.json()["error"]["message"]
    assert count(User) == len(seed.DEMO_ACCOUNTS)  # nothing was created
    login = {"email": "owner@example.com", "password": seed.DEMO_PASSWORD}
    assert client.post("/api/v1/auth/login", json=login).status_code == 200


def test_sign_up_works_outside_the_demo(client):
    assert client.post("/api/v1/auth/signup", json=SIGNUP).status_code == 201


# ── Seed and reset scripts ──────────────────────────────────────────────────


def test_seeding_refuses_production_unless_it_is_the_demo(env, capsys):
    env(ENVIRONMENT="production")
    assert seed.main() == 1
    assert seed_sample_history.main(["--csv", "unused.csv"]) == 1
    assert "DEMO_MODE is off" in capsys.readouterr().err
    assert count(Organization) == 0

    env(ENVIRONMENT="production", DEMO_MODE="true")
    assert seed.main() == 0
    assert count(User) == len(seed.DEMO_ACCOUNTS)


def test_reset_needs_the_flag_and_refuses_real_production(env, capsys):
    seed.main()
    assert reset_demo.main([]) == 1
    env(ENVIRONMENT="production")
    assert reset_demo.main(["--yes-delete-everything"]) == 1
    assert count(Organization) == 1  # untouched both times
    assert "--yes-delete-everything" in capsys.readouterr().err


def test_reset_empties_everything_and_seeds_the_demo_store(env, client, headers):
    seed.main()
    # Changes a visitor might make, including an append-only activity log entry.
    product = client.post(
        "/api/v1/products",
        json={"name": "Visitor item", "sku": "VIS-1", "price": "5.00", "cost": "4.00",
              "reorder_level": 1, "initial_stock": 3},
        headers=headers,
    ).json()  # fmt: skip
    client.patch(f"/api/v1/products/{product['id']}", json={"price": "6.00"}, headers=headers)
    assert count(AuditEvent) == 1 and count(Organization) == 2

    env(ENVIRONMENT="production", DEMO_MODE="true")
    assert reset_demo.main(["--yes-delete-everything"]) == 0

    assert count(AuditEvent) == 0
    with SessionLocal() as db:
        assert [org.id for org in db.scalars(select(Organization))] == [seed.DEMO_ORG_ID]
    assert count(User) == len(seed.DEMO_ACCOUNTS)

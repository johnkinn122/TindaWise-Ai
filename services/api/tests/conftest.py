"""Test setup: a real PostgreSQL test database, migrated with Alembic, wiped between tests.

Tests use PostgreSQL (not SQLite) on purpose: row locks, partial unique indexes and CHECK
constraints are part of what is being tested.
"""

import os
import uuid
from collections.abc import Iterator

# Must happen before any `app` import: the engine is created from DATABASE_URL at import time.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://tindawise:tindawise_dev@localhost:5433/tindawise_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Membership, Organization, Role, User  # noqa: E402
from app.schemas.auth import LoginRequest  # noqa: E402
from app.services.auth import login  # noqa: E402

TEST_PASSWORD = "correct-horse-battery"

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    """Rebuild the schema from migrations once per run, proving the migrations work."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    config = Config(os.path.join(API_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(API_ROOT, "migrations"))
    config.cmd_opts = type("Opts", (), {"x": [f"url={TEST_DATABASE_URL}"]})()
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE sessions, memberships, users, stock_movements, products, categories, "
                "organizations CASCADE"
            )
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client


def _make_org(name: str) -> Organization:
    with SessionLocal() as db:
        org = Organization(id=uuid.uuid4(), name=name, currency="PHP")
        db.add(org)
        db.commit()
        return org


@pytest.fixture
def org() -> Organization:
    return _make_org("Test Store A")


@pytest.fixture
def other_org() -> Organization:
    return _make_org("Test Store B")


def make_member(org: Organization, role: Role, email: str | None = None) -> User:
    """Create a user with a role in `org` (password: TEST_PASSWORD)."""
    with SessionLocal() as db:
        user = User(
            email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            full_name=f"Test {role.value}",
            password_hash=hash_password(TEST_PASSWORD),
        )
        db.add(user)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role=role.value))
        db.commit()
        return user


def auth_headers(org: Organization, role: Role) -> dict[str, str]:
    """Sign in a fresh member of `org` with `role` and return its Authorization header."""
    user = make_member(org, role)
    with SessionLocal() as db:
        _, token = login(db, LoginRequest(email=user.email, password=TEST_PASSWORD))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers(org: Organization) -> dict[str, str]:
    """Signed in as the owner of `org`."""
    return auth_headers(org, Role.OWNER)


@pytest.fixture
def other_headers(other_org: Organization) -> dict[str, str]:
    """Signed in as the owner of a different organization."""
    return auth_headers(other_org, Role.OWNER)


@pytest.fixture
def make_product(client: TestClient, headers: dict[str, str]):
    counter = {"n": 0}

    def _make(**overrides) -> dict:
        counter["n"] += 1
        payload = {
            "name": f"Product {counter['n']}",
            "sku": f"SKU-{counter['n']:03d}",
            "price": "10.00",
            "cost": "8.00",
            "reorder_level": 5,
            "initial_stock": 20,
        } | overrides
        response = client.post("/api/v1/products", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _make

# Tindawise API

FastAPI backend for products, categories and inventory. See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md).

## First-time setup (Windows, from `services/api`)

```bash
# 1. Start PostgreSQL (from the repo root)
docker compose -f infrastructure/docker-compose.yml up -d

# 2. Python 3.13 virtual environment
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env

# 3. Create the tables, then add the sample store
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m scripts.seed
```

## Run

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

- Interactive docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Every `/api/v1` endpoint except sign-up and sign-in needs `Authorization: Bearer <token>`.
Get a token from `POST /api/v1/auth/login`. The seed creates demo accounts for local use only:
`owner@example.com`, `manager@example.com`, `cashier@example.com`, all with password
`tindawise-demo` (public, so never seed a real server with them).

## Checks

```bash
.venv/Scripts/python -m pytest      # uses the tindawise_test database
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
```

## Database changes

```bash
# after editing app/models/*
.venv/Scripts/alembic revision --autogenerate -m "describe the change"
# read the generated file in migrations/versions/ before applying it
.venv/Scripts/alembic upgrade head
```

## Endpoints (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/signup` | Create an account + store; signs in as owner |
| POST | `/api/v1/auth/login` | Sign in; returns a session token (shown once) |
| POST | `/api/v1/auth/logout` | Revoke the current session |
| GET | `/api/v1/auth/me` | Current user, store and role |
| GET / POST | `/api/v1/members` | List / add team members (owner only) |
| GET | `/api/v1/categories` | List categories |
| POST | `/api/v1/categories` | Create a category |
| GET | `/api/v1/products` | List products: `q`, `category_id`, `status`, `include_archived`, `sort`, `limit`, `offset` |
| POST | `/api/v1/products` | Create a product (optional `initial_stock`) |
| GET | `/api/v1/products/{id}` | Get one product |
| PATCH | `/api/v1/products/{id}` | Update details (not stock) |
| DELETE | `/api/v1/products/{id}` | Archive (soft delete) |
| POST | `/api/v1/products/{id}/stock-adjustments` | Change stock. Send an `Idempotency-Key` header to make retries safe |
| GET | `/api/v1/products/{id}/movements` | Stock history, newest first |

Errors always look like `{"error": {"code", "message", "fields"}}`.

# Tindawise AI

A retail operations platform for small and medium stores in the Philippines: products, stock,
and (planned) sales, suppliers, demand forecasting and an AI business copilot.

> **Status:** early development. Built so far: sign-in with owner/manager/cashier roles,
> Products, Point of Sale, sales history with refunds, an Overview dashboard, suppliers and
> purchase orders, Reports, and an inventory ledger that prevents overselling. Everything else is planned; see [Roadmap](#roadmap).

## What works today

- **Accounts:** sign up (creates your store), sign in, sign out; owners add managers and cashiers.
- **Store settings:** the owner sets the store name, time zone and default delivery time (used by
  reorder suggestions); managers can view them.
- **Roles:** owners and managers run products, stock and purchasing; only the owner approves purchase
  orders; everyone can sell, and cashiers never see costs. Enforced by the API.
- **Point of Sale:** scan or search, cart, cash with change or e-wallet reference, printable receipt.
  Stock drops with every sale, and a sale is all-or-nothing.
- **Sales history and refunds:** every receipt, searchable by number. Owners and managers refund
  some or all items, with a reason, choosing per item whether it goes back on the shelf. Sales,
  profit and reports are net of refunds. Cashiers see their own receipts.
- **Overview:** today's sales, transactions and gross margin against the same day last week, this
  week's sales by day, stock to watch, and reorder suggestions from recent sales and each
  supplier's delivery time, each with its reason. Days follow the store's
  time zone. Cashiers see their own sales and no costs.
- **Suppliers and purchase orders:** draft an order (or one click from the Overview's reorder
  suggestions), the owner approves it, then record deliveries as they arrive, including partial
  deliveries and closing an order short. Receiving adds stock and updates each product's cost.
- **Reports:** any period (presets or a custom range) against the period before: sales, gross
  profit and margin, sales by day/week/month, top products, categories, payment methods and
  purchases by supplier, with CSV downloads. Owners and managers only.
- **Products:** search, filter by stock status and category, sort, paginate, add, edit, archive.
- **Inventory:** stock adjustments with reasons (received, returned, damaged, sold, count correction)
  and a full stock history per product. The Inventory page shows stock value, units on hand, low and
  out-of-stock counts, and a store-wide ledger of every stock change, filterable by product, reason,
  person and dates, each linked to its sale, refund or purchase order. Owners and managers only.
- **Safety:** stock can't go below zero even with simultaneous sales (row locks + database checks),
  retried requests are applied once (idempotency keys), and money is stored as exact decimals.
- **Accessibility:** WCAG 2.2 AA checks run automatically in light and dark mode.
- **Forecasting (not in the app yet):** export a store's daily demand from the database and score
  baselines and a LightGBM model on it (`services/ml`). An opt-in sample store with two years of
  synthetic sales lets you try it (see `services/api/README.md`).

## Stack

| Layer | Technology |
|---|---|
| Web | Next.js 16 (App Router, Cache Components), TypeScript, Tailwind CSS v4, shadcn/ui, Recharts |
| API | FastAPI, Pydantic v2, SQLAlchemy 2.1, Alembic, Python 3.13 |
| Database | PostgreSQL 17 + pgvector (Docker) |
| ML | Python 3.13, pandas, NumPy, LightGBM (forecasting experiments, not in the app yet) |
| Tests | Vitest, Testing Library, Playwright + axe-core, pytest, Ruff, ESLint |
| CI | GitHub Actions |

## Run it locally

Requirements: Node 22+, Python 3.13, Docker.

```bash
# 1. Database
docker compose -f infrastructure/docker-compose.yml up -d

# 2. API (first time only; see services/api/README.md)
cd services/api
py -3.13 -m venv .venv                 # macOS/Linux: python3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
cp .env.example .env
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m scripts.seed   # sample store with 17 sample products
cd ../..

# 3. Web
npm install
cp apps/web/.env.example apps/web/.env.local

# 4. Start both (two terminals)
npm run dev:api    # http://localhost:8000/docs
npm run dev:web    # http://localhost:3000
```

Sign in with a demo account from the seed (local only): `owner@example.com`,
`manager@example.com` or `cashier@example.com`, password `tindawise-demo`. Or create your own
store at `/signup`.

## Checks

| Command | What it runs |
|---|---|
| `npm run typecheck:web` | Route type generation + TypeScript |
| `npm run lint:web` | ESLint |
| `npm run test:web` | Vitest unit and component tests |
| `npm run test:e2e` | Production build + Playwright (needs the database running) |
| `npm run lint:api` | Ruff lint + format check |
| `npm run test:api` | pytest on a real PostgreSQL test database |
| `npm run lint:ml` | Ruff lint + format check for `services/ml` |
| `npm run test:ml` | pytest for `services/ml` (no database; setup in `services/ml/README.md`) |
| `npm run backtest:ml` | Score the baselines and LightGBM on synthetic history (about 10 s) |
| `npm run tune:ml` | Score LightGBM settings on the validation period (a few minutes; not in CI) |
| `npm run policies:ml` | Replay the test period with the current reorder rule vs forecast-based ordering (a few minutes; not in CI) |

CI runs all of them on every pull request.

## Repository layout

```
apps/web/          Next.js frontend
services/api/      FastAPI backend
services/ml/       Forecasting experiments (synthetic data, baselines, LightGBM, backtest)
infrastructure/    docker-compose for local services
design-system/     Design rules (MASTER.md), tokens, visual preview
docs/              ARCHITECTURE.md, DEVELOPMENT_LOG.md, ml/EXPERIMENTS.md
```

## Roadmap

1. **Core platform**: ✅ products and inventory · ✅ sign-in and roles · ✅ point of sale ·
   ✅ real Overview · ✅ suppliers and purchase orders · ✅ reports · ✅ sales history and refunds ·
   ✅ inventory page (store-wide ledger)
2. **Machine learning** (in progress): ✅ forecasting baselines and backtest on synthetic data ·
   ✅ LightGBM forecaster (synthetic data) · ✅ demand export from the database ·
   ✅ reorder policy simulation (synthetic data) · ✅ demand-based reorder suggestions in the app ·
   📋 anomaly detection
3. **AI agents** (planned): business copilot, purchase-order drafts with human approval
4. **Deployment** (planned)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design decisions and
[`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md) for what was built, how it was verified,
and known issues.

# Tindawise AI — Architecture

> Status legend: ✅ built · 🚧 in progress · 📋 planned

## Repository layout

```
tindawise-ai/
├── apps/
│   └── web/                 ✅ Next.js frontend: Overview, Products, Point of Sale, Suppliers, Purchase orders, Reports
├── services/
│   ├── api/                 ✅ FastAPI backend: auth, products, inventory ledger, sales, overview, purchasing, reports
│   └── ml/                  🚧 Forecasting: synthetic history, baselines, backtest (models planned)
├── packages/                📋 Shared TypeScript types and UI used across apps
├── infrastructure/          🚧 docker-compose (PostgreSQL + pgvector); deploy planned
├── .github/workflows/       ✅ CI: web, api, e2e jobs
├── design-system/           ✅ Design source of truth (MASTER.md, tokens, preview)
└── docs/                    ✅ Architecture and development log
```

The root `package.json` defines **npm workspaces** (`apps/*`, `packages/*`), so one `npm install`
at the root installs every JavaScript app and shared package.

## Frontend — `apps/web`

| Concern | Choice | Notes |
|---|---|---|
| Framework | Next.js 16 (App Router, Turbopack) | `cacheComponents` + `partialPrefetching` enabled (Next 16 defaults) |
| Language | TypeScript, `strict: true` | `npm run typecheck` runs `next typegen` first so route types like `LayoutProps` exist |
| Styling | Tailwind CSS v4 | Tokens live in `src/app/globals.css`, mirrored from `design-system/tindawise-ai/tokens.css` |
| Components | shadcn/ui (Radix base) | Copied into `src/components/ui/` and owned by us. `button.tsx` is adjusted to the design spec |
| Charts | Recharts 3 | Colors come from `--chart-*` CSS variables, so charts follow light/dark mode |
| Icons | lucide-react | 1.5px stroke, decorative icons are `aria-hidden` |
| Fonts | `next/font/google` | Bricolage Grotesque (display) + IBM Plex Sans (UI) |

### Source structure

```
src/
├── app/
│   ├── layout.tsx              Root: fonts, theme init script, TooltipProvider
│   ├── globals.css             Design tokens + Resibo card styles
│   └── (dashboard)/            Route group: shares the app shell, not part of the URL
│       ├── layout.tsx          Sidebar + top bar + <main>
│       ├── page.tsx            "/" Overview (live: KPIs, week chart, stock to watch, reorder list)
│       ├── error.tsx           Fallback error screen inside the shell
│       ├── products/           Live: list, /new, /[id] (detail + stock), /[id]/edit, actions.ts
│       ├── sell/               Live: checkout screen, products/route.ts (lookup for the browser), actions.ts
│       ├── suppliers/          Live: list, /new, /[id]/edit (archive there), actions.ts
│       ├── purchase-orders/    Live: list (status tabs), /new, /[id] (actions, deliveries, history), /[id]/edit
│       ├── reports/            Live: period presets + custom range, KPIs, charts, tables; export/route.ts (CSV)
│       ├── sales/              Live: receipt list + search, /[id] (receipt, refunds, refund form), actions.ts
│       └── inventory/          Live: stock KPIs + store-wide ledger with filters (owners and managers)
├── components/
│   ├── ui/                     shadcn primitives (button, table, sheet, badge, tooltip, separator)
│   ├── layout/                 App shell: sidebar, mobile drawer, top bar, nav, theme toggle
│   ├── dashboard/              Overview building blocks: KPI strip, chart, stock table, reorder card,
│   │                           Resibo card (AI only; unused until the ML phase)
│   └── products/               Filters, table, pagination, product form, stock form, archive dialog
└── lib/
    ├── api/                    server-only API client + typed product endpoints
    ├── format.ts               Peso / number / percent formatting (en-PH)
    ├── overview.ts             Overview response → KPI wording, chart rows, axis ticks (unit-tested)
    ├── sample-data.ts          SAMPLE DATA ONLY: the AI reorder suggestion for the Resibo card
    └── utils.ts                cn() class merging
```

### Key decisions

- **Server components by default.** Only components that need browser state are client components:
  `NavLinks` (active route), `MobileNav` (drawer state), `ThemeToggle`, `SalesChart` (Recharts + table toggle).
- **Dark mode without a dependency.** A tiny inline script in `<head>` sets the `dark` class before first
  paint (no flash). The toggle saves the choice to `localStorage`; with no saved choice, the OS setting wins.
- **Sample data is quarantined.** All demo numbers live in `src/lib/sample-data.ts`, and every screen
  using them shows a "Sample data" badge. This follows the rule never to present invented analytics as real.
- **The browser never talks to the API directly.** Server Components read through `lib/api/*`
  (marked `server-only`) and Server Actions write through it. `API_URL` lives in `.env.local`
  without a `NEXT_PUBLIC_` prefix, so it never reaches the client.
- **Sessions:** the API token sits in an httpOnly, SameSite=Lax cookie (`tw_session`, Secure in
  production) that page scripts can't read. `apiFetch` forwards it as a Bearer token; a 401 sends the
  person to `/login?reason=session`. `src/proxy.ts` redirects signed-out visitors to `/login?next=…`
  before rendering (an optimistic check only; the API is the real gate). `next` is validated so it
  can only point inside the app (no open redirects).
- **Who is signed in** comes from `getCurrentUser()` (React `cache`, one `/auth/me` call per request),
  always read inside `<Suspense>`, so the shell still prerenders. Role-aware UI hides actions a role
  can't take, but the API enforces the same rules.
- **Pages are Partial Prerenders.** With Cache Components on, each Products page ships a static shell
  (header, panel frames, skeletons) and streams API data inside `<Suspense>`. Client hooks that read
  the URL (`usePathname`, `useSearchParams`) also sit inside Suspense boundaries.
- **Filters live in the URL** (`?q=&status=&category=&sort=&page=`), so views are shareable and the
  back button works.
- **Forms work like the API.** Field errors from the API (`error.fields`) render under their fields,
  focus moves to an error summary, and typed values are kept after a failed submit.
- **Stock changes are idempotent from the UI too.** The stock form creates an `Idempotency-Key` at
  submit time, so a double submit or network retry is applied once.
- **AI actions stay inert until approval exists.** "Create purchase order" is disabled until the
  backend has purchase orders with a human-approval flow (claude.md §9).
- **Rules are not dressed up as AI.** The Overview's reorder list is a fixed rule, so it uses a plain
  panel, not the Resibo receipt look, which MASTER.md §7 reserves for AI output. There is no forecast
  line on the sales chart until a model exists.

## Backend — `services/api`

| Concern | Choice | Notes |
|---|---|---|
| Framework | FastAPI | Sync endpoints (run in a thread pool); simple to reason about for now |
| Validation | Pydantic v2 | Money is `Decimal` with 2 places, serialized as a string |
| Database | PostgreSQL 17 + pgvector (Docker, host port 5433) | pgvector is ready for the AI copilot phase |
| ORM / migrations | SQLAlchemy 2.1 + Alembic | Constraint naming convention gives stable migration names |
| Tests / lint | pytest (real PostgreSQL `tindawise_test` DB) + Ruff | Schema is rebuilt from migrations every run |

### Layers

```
app/
├── api/          HTTP only: routes, query params, status codes. No business rules.
│   ├── deps.py   DB session, signed-in session (Bearer token), role checks
│   └── v1/       auth.py, members.py, categories.py, products.py, sales.py, overview.py,
│                 suppliers.py, purchase_orders.py, reports.py, inventory.py
├── services/     Business rules. Never imports FastAPI; raises domain errors.
│   ├── auth.py        sign-up, sign-in, sessions, team membership
│   ├── sales.py       checkout: prices from the DB, all-or-nothing, receipt numbers
│   ├── overview.py    dashboard figures: store-local days, comparisons, reorder rule
│   ├── suppliers.py   supplier list/search, unique names per store (case-insensitive), archive
│   ├── purchase_orders.py  draft → approve → receive; locks, idempotency, latest-cost rule
│   ├── reports.py     sales report: periods, buckets, products, categories, payments, purchases
│   ├── products.py    product + category rules, org-scoped queries
│   ├── refunds.py     refunds: receipt prices, restock or write off, locks, idempotency
│   ├── inventory_ledger.py  read-only: store-wide ledger with filters, stock summary
│   └── inventory.py   the ONLY place stock changes
├── models/       SQLAlchemy tables
├── schemas/      Pydantic request/response shapes
├── core/         settings, password + token hashing, domain errors → JSON error shape
└── db/           engine, session, declarative base
```

### Data model

```
users ─┬─< memberships >─ organizations ─┬─< categories
       │   (role: owner/manager/cashier) ├─< products ──< stock_movements (append-only ledger)
       └─< sessions (token hash only)    ├─< stock_movements.created_by_user_id → users
                                         ├─< sales ──< sale_lines (name/price/cost snapshots)
                                         │     ├──< stock_movements.sale_id
                                         │     └──< refunds ──< refund_lines (→ sale_lines, price/cost copied)
                                         │            └──< stock_movements.refund_id (restocked units)
                                         ├─< suppliers
                                         └─< purchase_orders ──< purchase_order_lines (name/SKU/unit snapshots)
                                               │  (supplier_id → suppliers, null only on drafts)
                                               └──< purchase_order_receipts (one per delivery)
                                                     └──< stock_movements.purchase_order_receipt_id
```

- **Organization isolation:** every query filters by `organization_id`. A record from another
  organization returns 404, never 403, so its existence isn't revealed.
- **Money:** `NUMERIC(12,2)` + `CHAR(3)` currency (PHP). Never floats.
- **Stock:** `products.stock_on_hand` is a cached balance; `stock_movements` records every change
  with `balance_after`. Both are written in one transaction.
- **No overselling:** the product row is locked (`SELECT … FOR UPDATE OF products`) before a change,
  and `CHECK (stock_on_hand >= 0)` backs it up in the database. Tested with 10 concurrent sales on 5 units.
- **No double-applied retries:** an optional `Idempotency-Key` header is stored on the movement with a
  unique constraint per organization. A replay returns the original movement with HTTP 200.
- **Nothing is hard-deleted:** products are archived (`is_active = false`); movements are never edited.
- **Store time zone:** `organizations.timezone` (IANA name, default `Asia/Manila`) decides where a
  day starts for reports. Postgres converts each sale's timestamp to the local date, so a sale at
  00:30 Manila time counts for that day even though it is still the previous day in UTC.

### Purchase orders (`/api/v1/purchase-orders`)

```
draft ──approve (owner)──▶ approved ──receive──▶ partially_received ──receive──▶ received
  │                           │                        │
  └──cancel (owner/manager)   └──cancel (owner)        └──close short ──▶ closed
```

- **Who:** owners and managers draft, edit drafts, receive and close short. Only the owner approves
  (`CanApprovePurchases`), and only the owner cancels an approved order. Cashiers get 403 on
  suppliers and purchase orders.
- **Lines lock at approval.** Only drafts can be edited; a draft may have no supplier yet, but
  approval requires an active one (also a database CHECK).
- **Receiving** locks the order row, then the products in id order (same lock order as checkout),
  adds stock through `record_movement` as `purchase` movements tied to a `purchase_order_receipts`
  row, and sets each product's cost to the order's unit cost (**latest-cost rule**; past sales keep
  their own cost snapshot). `CHECK (quantity_received <= quantity_ordered)` backs the over-receive
  check. Tested with 4 concurrent deliveries of 6 on an order of 10: exactly one succeeds.
- **Retries:** `Idempotency-Key` on create, from-reorder and receive; a replay returns the original
  order with HTTP 200.
- **Numbers:** `PO-000001`, per store, from `organizations.last_po_number` under a row lock.
- **From the Overview:** `POST /purchase-orders/from-reorder` drafts every current reorder
  suggestion at today's costs (the same `reorder_candidates` function the Overview uses).

### Sales report (`GET /api/v1/reports/sales`)

Owners and managers only (it is built on costs). Query: `preset` (today, yesterday, last_7_days,
last_30_days, this_month, last_month) or `start` + `end` (store days, both included, at most
366 days; a custom range wins), `product_sort` (sales, gross_profit, quantity), `top` (1–500).

| Figure | Definition |
|---|---|
| Period | Calendar days in the store's time zone, resolved by the API (so "today" is the store's day) |
| Comparison | The same number of days, ending the day before the period starts |
| Gross sales / refunds | Sale totals rung up in the period; refunds given in the period, whenever the sale was |
| Sales (net) | Gross sales − refunds. Closed periods never change, because a refund counts on its own day |
| Net cost | Cost copied onto each sale line − cost of refunded units put back on the shelf (units not restocked stay a loss) |
| Gross profit / margin | Net sales − net cost; profit ÷ net sales (no margin when net sales ≤ 0) |
| Average sale | Gross sales ÷ number of sales (the basket at checkout) |
| Items, products, categories, payments | Net of refunded units and amounts; a product can show a negative line |
| Buckets | By day up to 31 days, by week (Sunday start) up to 182, by month beyond; zero-filled |
| Category | The product's category **today** (sales don't record it) |
| Purchases | Stock received on purchase orders in the period × the order line's unit cost |

The web page reads it once per view; every panel shows the same slice. CSV exports run through
`/reports/export` (a Next.js route handler with the signed-in session), which protects against
spreadsheet formula injection: text cells starting with `= + - @` get a leading apostrophe.

### Overview figures (`GET /api/v1/overview`)

| Figure | Definition |
|---|---|
| Sales, transactions | Net sales (sale totals − refunds given that day) and number of sales on the store's current local day |
| Comparison | Same weekday one week earlier. No sales then → no percentage is shown |
| Gross margin | (net sales − net cost) / net sales; net cost gives back the cost of restocked refunded units. Products saved with cost 0 overstate it |
| Week chart | Sunday to Saturday, local days; days that haven't happened are `null`, not 0 |
| Stock to watch | Active products with stock ≤ reorder level; out of stock first, then lowest share of the level |
| Reorder quantity | Rule, not a forecast: reach max(2 × reorder level, units sold − units refunded in the last 14 days). Omitted when that is 0 |

Cashiers get the same response shape with `sales_scope: "mine"` (their own sales only, matching the
sales list), `costs_visible: false`, and every cost-derived field (`gross_margin`, `unit_cost`,
`estimated_cost`) set to `null` by the API, not just hidden in the UI.

### Checkout (Point of Sale)

- **The server prices the sale.** The client sends product ids and quantities only; prices and
  costs come from the database. Each line stores a snapshot of name, SKU, unit, price and cost, so
  old receipts and profit stay correct after prices change.
- **All or nothing.** Every product in the cart is locked (`FOR UPDATE`, in id order so concurrent
  checkouts can't deadlock) before stock is checked. If any item is short, nothing is recorded.
  Tested with 8 concurrent checkouts in different cart orders against 3 units: exactly 3 succeed.
- **Receipt numbers** (`S-000001`) are sequential per store, taken from
  `organizations.last_receipt_number` under a row lock.
- **Payments:** cash (must cover the total; change is computed and stored) or e-wallet (GCash/Maya
  reference recorded; no payment processing). A CHECK constraint enforces the cash rule in the database.
- **Retries:** an `Idempotency-Key` per checkout attempt; a replay returns the original sale.
- **Every role can sell.** Cashiers see only their own sales; owners and managers see all.
- **Barcode scanners** type the code and press Enter: `GET /products/lookup?code=` matches the
  barcode exactly, then the SKU case-insensitively.
- Not yet: VAT computation, discounts, voids, offline mode, receipt printer integration
  (printing uses the browser's print dialog with a 72 mm receipt layout).

### Refunds (`POST /api/v1/sales/{id}/refunds`)

- **Who:** owners and managers (`CanManageInventory`). Cashiers get 403 and see no refund button.
- **The sale is never edited.** A receipt collects refunds (partial ones allowed) until every unit is
  refunded. `sale_lines.quantity_refunded` and `sales.refunded_total` are running totals, backed by
  CHECKs (`quantity_refunded <= quantity`, `refunded_total <= total`).
- **The receipt sets the amount.** Price and cost are copied from the receipt line, so a refund pays
  back exactly what was charged. The money goes back the way the sale was paid.
- **Restock or not, per line.** Restocked units go back into stock as `return` movements linked to
  the refund. Damaged or spoiled units don't change stock, and their cost stays a loss in reports.
- **Concurrency:** the sale row is locked first, then products in id order, then the organization
  (for the `R-000001` counter). Checkout never locks an existing sale, so the two can't deadlock.
  Two refunds on one receipt run one after the other, and the second sees what the first refunded.
- **Retries:** `Idempotency-Key` per refund attempt (unique per store). A replay returns the receipt
  with HTTP 200, and a key reused on a different receipt is a 409.

### Inventory (`GET /api/v1/inventory/movements`, `GET /api/v1/inventory/summary`)

Read-only views of the `stock_movements` ledger. Owners and managers only (`CanManageInventory`):
the ledger shows who changed stock and the summary shows stock value at cost. Cashiers get 403
and see stock levels on the product list instead.

| Figure | Definition |
|---|---|
| Ledger | Every movement in the store, newest first (`created_at`, then id), 25 per page by default |
| Filters | `reason`, `q` (product name or SKU, partial, LIKE wildcards escaped), `product_id`, `user_id`, `start`/`end` (store days, both included; end before start is a 422) |
| Source | The sale (`S-000123`), refund (`R-000007`, linked to its receipt) or purchase order (`PO-000004`) behind a movement; none for opening stock and adjustments |
| Stock value | Σ units on hand × each product's **current** cost (latest-cost rule), active products only. An estimate, not FIFO |
| Low / out of stock | Same thresholds as the product list: 1 … reorder level / 0 |
| People | Members who have changed stock in this store (the "who" filter offers only names that match something) |

- One query joins each movement to its product, author, sale, refund and delivery (outer joins),
  so a page costs two queries (count + rows) however many sources it shows.
- Index `ix_stock_movements_organization_created (organization_id, created_at)` serves the
  newest-first scan and date ranges.
- The web page is a plain GET form: every view has a URL. Empty fields are dropped by a redirect,
  so a shared link only says what is filtered.

### Authentication and roles

- **API-owned sessions.** `POST /auth/login` returns a random 256-bit token once; the database stores
  only its SHA-256 hash, so a database leak doesn't hand out working sessions. Sessions expire after
  30 days and are revoked on sign-out.
- **Passwords** are hashed with Argon2id (`argon2-cffi`) and rehashed when parameters change.
  Unknown emails still run a hash check, and every failure returns the same message, so responses
  don't reveal which emails have accounts.
- **The organization comes from the session**, never from the request. Every endpoint except
  sign-up and sign-in requires `Authorization: Bearer <token>`.
- **Roles are checked on the server** for every request (`require_roles` dependency):

  | Action | Owner | Manager | Cashier |
  |---|---|---|---|
  | View products, stock, history | ✅ | ✅ | ✅ |
  | Add / edit / archive products, adjust stock, add categories | ✅ | ✅ | — |
  | Manage the team | ✅ | — | — |

- **Audit:** every stock movement records `created_by_user_id`.
- **Team:** owners add managers/cashiers with a temporary password. An email that already has an
  account is refused rather than attached, so nobody can pull another person's account into a store.

### Known limitations

- No rate limiting on sign-in yet (needs Redis; planned).
- No password reset, email verification, or switching between stores yet.
- Quantities are whole units (no fractional kilos or liters yet).
- Windows: `uvicorn --reload` used to watch `.venv` too, so pytest runs triggered reloads that hung
  and left old code serving port 8000. `npm run dev:api` now passes `--reload-dir app`. If an old
  server is still around, stop every `python … uvicorn` / `multiprocessing` process and restart.

## Testing and CI

| Level | Tool | Where | Covers |
|---|---|---|---|
| Unit / component | Vitest + Testing Library (jsdom) | `apps/web/test/unit` | formatters, URL guards, API client errors, components |
| API | pytest on real PostgreSQL | `services/api/tests` | rules, constraints, concurrency, idempotency, isolation |
| End-to-end | Playwright (Chromium, desktop + Pixel 7) | `apps/web/test/e2e` | product lifecycle, forms, filters, navigation, mobile drawer |
| Accessibility | axe-core in Playwright | `apps/web/test/e2e/accessibility.spec.ts` | WCAG 2.2 A/AA rules, light + dark |
| ML | pytest (no database) | `services/ml/tests` | metrics, data contract, synthetic history, baselines, leakage |

`.github/workflows/ci.yml` runs four jobs on every PR: **web** (types, lint, unit, build),
**api** (Ruff, pytest with a PostgreSQL service), **ml** (Ruff, pytest with warnings as errors,
and a backtest smoke run), and **e2e** (needs web and api: migrates and seeds a fresh database,
then runs Playwright against the production build and the API).

### Cache Components and hidden pages

With Cache Components, Next.js keeps recently visited pages mounted but hidden (React `<Activity>`).
Consequences handled in the code:

- **Ids must be unique per instance.** Form fields and panels use `useId()`, so a hidden copy of a
  page can't steal a `<label for>` or `aria-labelledby` target.
- **State survives navigation.** The product form resets itself when hidden; the search box resyncs
  from the URL; the stock form doesn't replay an old "Stock updated" message.
- **Tests use `getByRole`**, which ignores hidden elements, instead of `getByLabel`.

## Machine learning — `services/ml`

🚧 Forecasting baselines and their backtest are built. Nothing is wired into the API or the web
app yet. Results: [`docs/ml/EXPERIMENTS.md`](ml/EXPERIMENTS.md).

- **Separate Python package** (`tindawise_ml`) with its own virtual environment and dependencies
  (numpy, pandas). It doesn't import the API, so ML libraries never end up in the API's install,
  and the API doesn't need them to start. When forecasts reach the app, the API will read
  stored results instead of importing model code. That's planned, not built.
- **One table contract** (`data.py`): one row per product per store-local day, zero-filled,
  with `units_sold` and a `stockout` flag. Every source (synthetic now, the database later) must
  produce it, and `validate_demand_frame` refuses gaps, duplicates, negative or fractional units.
- **Synthetic sample history** (`synthetic.py`): the demo store has no sales, so a seeded
  generator invents a history for the 17 demo SKUs. It produces the same table for the same
  seed, and each SKU has its own random stream. A stock simulation caps sales at what was on
  the shelf, so the data has censored demand like a real store. All its effects are assumptions,
  documented in the module.
- **Stockout flag = the product reached zero that day.** Real data can compute the same from
  `stock_movements`. Scoring skips those days, since sales there understate demand.
- **Chronological evaluation only** (`backtest.py`): rolling origins, each forecast seeing only
  sales up to its origin. A test changes every value after an origin and checks the forecasts stay
  identical. Another checks the synthetic-only `demand` column is never read.
- **Metrics:** MAE, RMSE and WAPE (`metrics.py`). WAPE pools products of different volumes and
  survives zero-sales days, where MAPE would divide by zero.
- **Baselines:** naive, seasonal naive (7 days), 28-day moving average. A model only counts as
  an improvement if it beats the best of these on the same test period.

| Planned next | Notes |
|---|---|
| LightGBM forecaster | Tuned on a validation period before the test period; test period used once |
| Database loader | Same table from `sale_lines` (units sold on the sale's store day) and `stock_movements` |
| Stockout risk and reorder quantities | Forecast vs stock on hand and lead time, replacing the fixed reorder rule |
| Anomaly detection | Unusual sales and stock movements |

## AI agents

📋 Not started. See `claude.md` §8–§9.

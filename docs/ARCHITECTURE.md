# Tindawise AI — Architecture

> Status legend: ✅ built · 🚧 in progress · 📋 planned

## Repository layout

```
tindawise-ai/
├── apps/
│   └── web/                 ✅ Next.js frontend: Overview, Products, Point of Sale, Suppliers, Purchase orders, Reports
├── services/
│   ├── api/                 ✅ FastAPI backend: auth, products, inventory ledger, sales, overview, purchasing, reports
│   └── ml/                  🚧 Forecasting: synthetic history, baselines, LightGBM, backtest
├── packages/                📋 Shared TypeScript types and UI used across apps
├── infrastructure/          ✅ docker-compose for local PostgreSQL + pgvector
├── render.yaml              🚧 Render Blueprint for the demo API (prepared, not deployed: docs/DEPLOYMENT.md)
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
│       ├── page.tsx            "/" Overview (live: KPIs, week chart, stock to watch, reorder list,
│       │                       "Worth a look" for owners and managers)
│       ├── actions.ts          Overview actions: dismiss an unusual-sales alert
│       ├── error.tsx           Fallback error screen inside the shell
│       ├── products/           Live: list, /new, /[id] (detail + stock), /[id]/edit, actions.ts
│       ├── sell/               Live: checkout screen, products/route.ts (lookup for the browser), actions.ts
│       ├── suppliers/          Live: list, /new, /[id]/edit (archive there), actions.ts
│       ├── purchase-orders/    Live: list (status tabs), /new, /[id] (actions, deliveries, history), /[id]/edit
│       ├── reports/            Live: period presets + custom range, KPIs, charts, tables; export/route.ts (CSV)
│       ├── sales/              Live: receipt list + search, /[id] (receipt, refunds, refund form), actions.ts
│       ├── settings/           Live: team/ (owner), store/ (owner edits; managers view), activity/ (owner)
│       └── inventory/          Live: stock KPIs + store-wide ledger with filters (owners and managers)
├── components/
│   ├── ui/                     shadcn primitives (button, table, sheet, badge, tooltip, separator)
│   ├── layout/                 App shell: sidebar, mobile drawer, top bar, nav, theme toggle
│   ├── dashboard/              Overview building blocks: KPI strip, chart, stock table, reorder card,
│   │                           "Worth a look" panel (streams in behind its own Suspense),
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
- **Rules are not dressed up as AI.** The Overview's reorder list comes from an average of recent
  in-stock sales with a safety buffer, not a model, so it uses a plain panel, not the Resibo
  receipt look, which MASTER.md §7 reserves for AI output. Each line says why it's suggested.
  There is no forecast line on the sales chart. The "Worth a look" panel (unusual sales days)
  follows the same rule: a ratio against a recent average, so a plain panel.

## Backend — `services/api`

| Concern | Choice | Notes |
|---|---|---|
| Framework | FastAPI | Sync endpoints (run in a thread pool); simple to reason about for now |
| Validation | Pydantic v2 | Money is `Decimal` with 2 places, serialized as a string |
| Database | PostgreSQL 17 + pgvector (Docker, host port 5433) | pgvector is installed but not used yet |
| ORM / migrations | SQLAlchemy 2.1 + Alembic | Constraint naming convention gives stable migration names |
| Tests / lint | pytest (real PostgreSQL `tindawise_test` DB) + Ruff | Schema is rebuilt from migrations every run |

### Layers

```
app/
├── api/          HTTP only: routes, query params, status codes. No business rules.
│   ├── deps.py   DB session, signed-in session (Bearer token), role checks
│   └── v1/       auth.py, members.py, categories.py, products.py, sales.py, overview.py,
│                 suppliers.py, purchase_orders.py, reports.py, inventory.py, store.py,
│                 audit.py, anomalies.py
├── services/     Business rules. Never imports FastAPI; raises domain errors.
│   ├── auth.py        sign-up, sign-in, sessions, team membership
│   ├── sales.py       checkout: prices from the DB, all-or-nothing, receipt numbers
│   ├── overview.py    dashboard figures: store-local days, comparisons
│   ├── reorder.py     reorder suggestions: recent in-stock sales, lead time, open orders
│   ├── anomalies.py   unusual sales days ("Worth a look"): ratio rule, dismissals
│   ├── shrinkage.py   stock going missing ("Worth a look"): count corrections vs sales
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
| Reorder suggestion | See "Reorder suggestions" below. Omitted when the quantity is 0 |

### Reorder suggestions (`app/services/reorder.py`)

Chosen by simulation (`docs/ml/EXPERIMENTS.md`, 2026-11-23): at about the same orders and stock as
the old fixed rule, it lost 45-73% fewer sales on six synthetic datasets, and the in-stock average
beat the plain average on all six. Per active product, from the last 28 complete store days
(the demand table in `demand_history.py`):

| Figure | Definition |
|---|---|
| Rate | Average units sold per day on in-stock days (stockout days left out) |
| Spread | Standard deviation of those days' sales |
| Lead time | `lead_time_days` of the supplier on the product's latest non-cancelled purchase order; otherwise the store's default delivery time (Store settings, 3 days unless changed) |
| On order | Σ (ordered − received) on draft, approved and partly received orders |
| Position | Stock on hand + on order |
| Suggest when | Position ≤ rate × lead time + buffer, where buffer = 1 × spread × √lead time |
| Quantity | ⌈rate × (lead time + 10) + buffer − position⌉ |
| Fallback | Fewer than 7 in-stock days (new products, or empty for weeks): when position ≤ reorder level, order up to 2 × reorder level |

- The Overview card and "Create purchase order from suggestions" use the same function, so they
  always agree. A draft made from the suggestions counts as on order, so the same items aren't
  suggested again.
- Units are counted as rung up: refunds don't lower the rate (the old rule subtracted them).
- 7 in-stock days is a judgment call; the simulation always had 28 days of history.

### Unusual sales days (`app/services/anomalies.py`, `GET /api/v1/anomalies`)

Chosen by experiment (`docs/ml/EXPERIMENTS.md`, 2026-11-23): on six synthetic datasets with planted
anomalies, a plain ratio beat a robust z-score and a negative binomial model. The fixed multiples
were rounded from the validation-period thresholds and scored once on the test periods.

| Figure | Definition |
|---|---|
| Days checked | The 7 complete store days before today (today isn't over, so it isn't checked) |
| Judged | Active products in stock that day (the shelf never reached zero) on a day the store was open, with 14+ such days in the 28 days before |
| Open | The store sold something that day (any active product). A day with no sales at all is a closed day, or the till wasn't used |
| Usual | Average units sold per day on those in-stock, open days |
| Spike | (sold + 1) ≥ 3 × (usual + 1) |
| Drop | (usual + 1) ≥ 7.5 × (sold + 1): for a zero day, a product that usually sells 6.5+ a day |

- **Computed on request, not stored.** Alerts always match the records, and there's no
  scheduler to run or keep in sync. Only dismissals are stored (`anomaly_dismissals`, one per
  product + store day + kind, enforced by a unique constraint).
- **Dismissing** (`POST /anomalies/dismissals`): only an alert on the current list can be
  dismissed (404 otherwise). A repeat returns the first dismissal (200), and simultaneous
  dismissals store one row and one audit event. Each dismissal goes to the activity log,
  with its optional note, because a dismissed alert can hide missing sales.
- **Owners and managers** (`CanReviewAnomalies`). Cashiers get 403: an alert can point at their
  own unrecorded sales.
- Units are counted as rung up, as in the demand table: a refunded duplicate still shows as a spike.
- **Closed days are skipped.** Without this, one holiday would flag every regular seller at once.
  Found on the sample history store (its sales stop the day before it was seeded). The
  experiment's synthetic data has no closed days, so its figures still apply.

### Stock going missing (`app/services/shrinkage.py`, same endpoint)

Chosen by experiment (`docs/ml/EXPERIMENTS.md`, "Shrinkage"): on simulated stores, the plain
share of sales beat a count of missing units and a Poisson test.

| Figure | Definition |
|---|---|
| Window | The 56 complete store days before today |
| Missing | Units removed by stock count corrections (`adjustment`), net of any a count found, when that's a loss. Recorded damage never counts |
| Sold | Units rung up in the window (refunds not subtracted) |
| Flag | Missing ≥ 5% × (sold + 1) |

- Returned in `GET /anomalies` as `stock_losses`, largest share first.
- **Dismissal key:** the store day of the latest count that found stock missing (kind
  `shrinkage`). A dismissed product comes back only when a later count finds more missing.
  Migration `0034c5890f56` widened `anomaly_dismissals.kind` and added the kind.
- It depends on the store counting stock. A product nobody counted shows nothing.

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

### Store settings (`GET/PATCH /api/v1/store`)

- Name, time zone and default delivery time. Managers read; only the owner changes them
  (`CanEditStore`). The store always comes from the session.
- **Time zone** must be an IANA name from the `tzdata` package (`Factory` and `localtime`
  excluded). It decides where every store day starts (Overview, Reports, ledger filters,
  reorder windows). Changing it rewrites nothing: past sales are regrouped into days in the new
  zone the next time a figure is computed.
- **Displayed times use the same zone.** `/auth/me` returns `organization.timezone`, and
  `formatDate` / `formatDateTime` (`lib/format.ts`) require a zone argument, so no screen can
  quietly fall back to a default. Calendar dates (report ranges, chart days) stay in UTC on
  purpose: they are days, not moments.
- **Currency is read-only.** Every price, cost and receipt is stored in it, and converting
  would need rules the app doesn't have.
- PATCH is partial; `null` means "not sent", because every setting is required.

### Audit log (`audit_events`, `GET /api/v1/audit-events`)

| Action | Recorded when |
|---|---|
| `store.updated` | A store setting actually changes (old and new values in `details`) |
| `member.added` | The owner adds a manager or cashier |
| `refund.created` | A refund is given (receipt, refund number, amount, units, reason) |
| `purchase_order.approved` / `.cancelled` / `.closed` | The order changes to that status |
| `product.price_changed` | A product's price or cost changes (old → new) |
| `product.archived` | An active product is archived |
| `anomaly.dismissed` | An owner or manager dismisses an unusual-sales or missing-stock alert (product, day, kind, figures, note) |

- **Append-only in the database.** A `BEFORE UPDATE OR DELETE` trigger raises an error for every
  row, whoever runs the statement, including raw SQL. Foreign keys to organizations and users
  are `RESTRICT`, so deleting either can't erase or rewrite the trail. (Both are archived,
  never deleted.)
- **Same transaction as the change.** `services/audit.record` only adds the row; the service
  commits it together with the change. A refused or rolled-back action leaves no entry, and
  an idempotent replay returns before `record`, so a retry is logged once.
- **Not logged here:** sales and stock changes. Receipts and the `stock_movements` ledger
  already record every one, with who made it.
- **Owner only** (`CanReviewAudit`): the log records what managers do, so the owner reviews it.
  Filters: action, person, store days. Newest first, paginated.
- `actor_user_id` is null only for actions without a signed-in person (reserved for scheduled
  jobs).

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
  | See store settings | ✅ | ✅ | — |
  | Change store settings (name, time zone, default delivery time) | ✅ | — | — |
  | Read the activity log | ✅ | — | — |

- **Audit:** every stock movement records `created_by_user_id`, and sensitive actions go to the
  append-only activity log (see "Audit log").
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
| ML | pytest (no database) | `services/ml/tests` | metrics, data contract, synthetic history, features, baselines, LightGBM, tuning split, leakage |

`.github/workflows/ci.yml` runs four jobs on every PR: **web** (types, lint, unit, build),
**api** (Ruff, pytest with a PostgreSQL service), **ml** (Ruff, pytest with warnings as errors,
and a backtest smoke run that trains LightGBM), and **e2e** (needs web and api: migrates and seeds a fresh database,
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

🚧 Built: baselines, a LightGBM forecaster, a chronological backtest, a reorder simulation,
sales anomaly experiments and shrinkage experiments, all on synthetic data. Two results are used in the app, each as a
plain rule re-implemented in the API (no model code is imported): reorder suggestions and
the "Worth a look" list of unusual sales days. Results: [`docs/ml/EXPERIMENTS.md`](ml/EXPERIMENTS.md).

- **Separate Python package** (`tindawise_ml`) with its own virtual environment and dependencies
  (numpy, pandas, LightGBM). It doesn't import the API, so ML libraries never end up in the API's install,
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
  survives zero-sales days, where MAPE would divide by zero. Bias (signed) is added because
  under-forecasting empties shelves and over-forecasting ties up cash, and the other three
  can't tell those apart. Each is reported per day and on **7-day totals per product**, which is
  what a reorder depends on and where daily noise partly cancels.
- **Oracle floor (synthetic only):** the generator's true mean demand, scored like a forecast.
  Its error is pure noise, so it shows how much room is left above any model.
- **Baselines:** naive, seasonal naive (7 days), 28-day moving average. A model only counts as
  an improvement if it beats the best of these on the same test period.
- **LightGBM forecaster** (`features.py`, `gbm.py`): one model for all products (the product is
  a categorical feature, so slow movers borrow patterns from fast ones), Poisson objective
  (counts, never negative). It is **direct multi-horizon**: a row is (origin, h, product), and
  its features come only from days up to the origin. That avoids feeding predictions back in,
  which compounds errors. Stockout days are dropped as labels so it doesn't learn to predict
  empty shelves. It is retrained at each origin, exactly as it would run live. Fixed seed and
  one thread make it repeatable.
- **Three-way split by date:** training | validation (84 days) | test (84 days). `tune` scores
  settings on validation only. The chosen settings are written into `gbm.DEFAULT_PARAMS` and
  run on test once.

- **Real data comes through the API service** (`app/services/demand_history.py`), which owns
  the schema, the store's time zone and organization isolation. `scripts.export_demand` writes
  the table as CSV, and `tindawise_ml.data.load_demand_csv` reads and validates it. The ML
  package has no database code, and its CI job needs no database.
  - `units_sold`: Σ `sale_lines.quantity` for sales on that store day. Refunds aren't
    subtracted: a return doesn't mean customers wanted less that day.
  - `stockout`: some movement that day ended at `balance_after = 0`, or nothing moved and the
    balance carried in was zero. A shelf restocked during the day after an empty night isn't
    flagged. Days before a product existed are flagged, so they're skipped too.
  - Active products only. Three grouped queries (units, per-day ledger summary with the last
    `balance_after`, opening balances via `DISTINCT ON`), then a zero-fill in Python.
- **Sample history store** (`scripts.seed_sample_history`, opt-in, refused in production): writes
  a synthetic history into a *separate* store (`…0002`, `sample-owner@example.com`) as deliveries,
  receipts and ledger rows. It isn't put in the demo store, because that store's ledgers already
  start with their opening stock and Playwright runs against it locally. Checked end to end:
  generate → seed → export gives back the identical table (12,410 rows, 0 differences), and
  the backtest scores match.

- **Reorder policy simulation** (`inventory.py`, synthetic only, because it needs true demand):
  replays the test period day by day (morning deliveries → sales capped by the shelf →
  evening orders arriving 1-3 days later) under the app's current rule or a forecast policy.
  Every policy faces the same demand and the same delivery-delay draws. Policies see only
  sales and stockout flags up to today, including the results of their own decisions. The
  forecast policy reorders when stock ≤ forecast demand over the 3-day lead time + a buffer
  (safety × spread of recent in-stock sales × √3), then orders up to lead + cover days of
  forecast + buffer. Forecasts are refreshed weekly. It reports fill rate, lost units,
  stockout days, days of stock and orders placed.

- **Anomaly detection** (`anomalies.py`, synthetic only): labelled anomalies are planted (spikes
  of +max(5, 3 × usual); zero-sale days, while in stock, for products that usually sell 3+ a
  day). Three detectors score every product-day from **earlier in-stock days only** (28-day
  windows shifted by a day; at least 14 days needed): a ratio baseline, a robust z-score
  (median/MAD) and a negative binomial tail probability. High and low are separate alerts with
  separate thresholds, chosen on the validation period and scored once on the test period.
  Result: the ratio baseline is the best on this data (`docs/ml/EXPERIMENTS.md`). `--fixed
  SPIKE_X DROP_X` scores it at fixed multiples, the form the app uses (3× and 7.5×).

- **Shrinkage** (`shrinkage.py`, synthetic only): a store simulation that keeps true and recorded
  stock, with unrecorded losses (a normal rate per product, plus planted problems), recorded
  damage, and stock counts every 14 days recorded as adjustments, as the app does. Sales need
  the unit on the shelf and in the records, and reorders follow recorded stock, so phantom stock
  happens. Detectors score each product weekly from the last 56 days of count corrections and
  sales. Thresholds are chosen on 10 validation **stores** and scored once on 6 separate test
  stores (a split by time left too few problems to choose from). Result: "missing units ≥ 5%
  of units sold" is best (`docs/ml/EXPERIMENTS.md`).

Both experiments' results are in the app ("Worth a look" on the Overview). Nothing else is
planned for this phase.

## Deployment (public demo)

🚧 Prepared, not deployed. Steps and limits: [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).

| Piece | Host | Why |
|---|---|---|
| Web | Vercel Hobby | Free for a non-commercial demo; made for Next.js |
| API | Render free web service (`render.yaml`, Singapore) | Free Python hosting; sleeps after 15 idle minutes |
| Database | Neon free (Singapore) | Free PostgreSQL that doesn't expire (Render's free database does after 30 days) |

- **`DEMO_MODE`** (API and web): sign-up off, a "public demo" banner, the demo accounts on the
  sign-in page, and the only way the seed and reset scripts may write to a production database.
  `Settings.sample_data_allowed` is the one rule both scripts check.
- **Migrations run as the API starts** (`alembic upgrade head && uvicorn …`), since pre-deploy
  commands are a paid Render feature.
- **Database URLs from hosts** (`postgresql://…`, `postgres://…`) are rewritten to the installed
  psycopg 3 driver; query parameters such as `sslmode=require` are kept.
- **Cold starts:** the sign-in page calls `wakeApiAction` (a Server Action that requests
  `/health`) as soon as it opens, so the API is usually awake by the time the visitor signs in.
- **Reset:** `scripts.reset_demo --yes-delete-everything` empties every table (TRUNCATE, which the
  activity log's append-only trigger doesn't block) and seeds the demo store again.


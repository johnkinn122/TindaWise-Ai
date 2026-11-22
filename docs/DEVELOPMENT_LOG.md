# Development Log

Newest entries first. Each entry records what was built, how it was verified, and what is still open.

---

## 2026-11-22 — Sales history and refunds (`feature/refunds`)

### Built
- Database (migration `8bbe9c689871`): `refunds` and `refund_lines` tables;
  `sales.refunded_total`, `sale_lines.quantity_refunded`, `organizations.last_refund_number`,
  `stock_movements.refund_id`. CHECKs: refunded units ≤ units sold, refunded total ≤ sale total,
  "other" needs a note, refund line total = price × quantity.
- API `POST /api/v1/sales/{id}/refunds` (owners and managers): partial or full refunds per
  receipt line, with a reason and an optional note. Each line can be restocked (stock goes back
  up as a `return` movement) or not (damaged or spoiled). The amount comes from the receipt's
  price snapshot, never from the client, and is paid back the way the sale was paid.
  `Idempotency-Key` makes a retry return the original refund. Numbers are `R-000001` per store.
- API `GET /api/v1/sales` takes `receipt=S-000123` (or `123`) and returns `refunded_total`;
  `GET /api/v1/sales/{id}` returns the receipt's refunds and its refund status.
- Reports and Overview are now **net of refunds** (formulas in `docs/ARCHITECTURE.md`):
  refunds count on the day they are given, restocked units give their cost back, and units not
  restocked stay a loss. Reports adds gross sales, refunds and the refund count; the reorder rule
  subtracts refunded units from recent sales.
- Web: **Sales history** in the sidebar (`/sales`): receipts newest first, find by number,
  refund status badges, pagination. Receipt page (`/sales/[id]`): items with sold and refunded
  quantities, Total / Refunded / Kept, the list of refunds, and a **Refund items** form that
  confirms the amount and payment method before submitting. The form keeps one idempotency key
  per refund attempt. Cashiers see their own receipts and no refund button.

### Verified
- pytest 141/141 (113 before), including 24 in `test_refunds.py`: partial and full refunds,
  over-refund 409, restock vs no restock, idempotent replay, key reused on another receipt,
  cashier 403, other store's receipt 404, concurrent refunds; plus new net-of-refund cases in
  the reports and overview tests.
- Vitest 106/106 (88 before). Playwright 80/80 (72 before): sell → find in sales history →
  partial refund with confirmation → stock restored; refund the rest without restocking → receipt
  closed, stock unchanged; today's report net of refunds; cashier sees no refund button; axe on
  Sales history (both themes), the receipt page and the refund form with errors showing.
- `npm run typecheck:web`, `npm run lint:web`, `npm run lint:api` pass. `alembic check`: models
  match migrations.
- Manual (running app): refund of 1 of 2 units through the API → 201; same key again → 200 and
  still one refund; refunding 2 more → 409; cashier → 403. Sales history and the receipt page
  checked in a browser at 1366px, no console errors.

### Known issues / open items
- No voids (cancelling a sale the same day) and no exchanges; an exchange is a refund plus a new sale.
- A refund can't be undone. A mistaken refund needs a stock adjustment and a new sale.
- No printable refund slip yet; the receipt page shows the refunds.
- Reports can show a negative line for a product in a period with more refunds than sales.
- Refunds aren't processed through GCash/Maya; the app records that money was paid back.

---

## 2026-11-22 — Reports (`feature/reports`)

### Built
- API `GET /api/v1/reports/sales` (owners and managers): a period from a preset or a custom
  range (resolved in the store's time zone), compared with the previous period of equal length;
  totals, zero-filled buckets by day/week/month, top products (sortable, `top` up to 500),
  categories, payment methods, and purchases received per supplier.
- The Overview's daily-totals query is now shared (`daily_totals`), so both screens sum sales
  the same way.
- Web `/reports`: preset links and a custom-range GET form (every view has a URL), KPI strip vs
  the previous period, sales columns with a table view, payment and category bar lists, sortable
  top-products table (`aria-sort`), purchases table, and CSV downloads through
  `/reports/export`.
- Shared helpers: `lib/compare.ts` (the "% vs …" wording, now used by the Overview too),
  `lib/chart.ts` (axis ticks), `lib/csv.ts` (formula-injection guard), `signedCents` for losses.

### Design notes
- Followed MASTER.md plus the dataviz and ui-ux-pro-max guidance: each chart shows one measure in
  one hue (chart-1), columns capped at 24px with 4px rounded tops, hairline grid, tooltips that
  lead with the value, a text summary and a table view for the chart, filters in one row above
  everything they scope.
- **Palette check (not changed, needs a decision):** the dataviz validator fails the two-series
  chart palette (chart-1 + chart-2): in light mode `#0F5C4D` is outside the lightness band and
  below the chroma floor; in dark mode `#4FBFA3` vs `#7FA6E8` is ΔE 14.9, just under the
  normal-vision floor of 15. Single-hue marks pass contrast. This affects the Overview's
  two-line chart; Reports avoids it by using one hue per chart.

### Verified
- pytest 113/113 (21 new: presets, previous period, custom-range errors, granularity, store-day
  boundary, zero-filled buckets, week/month grouping, product sort and limit, categories incl.
  "No category", payment methods, purchases by supplier, defaults, cashier 403, isolation).
- Vitest 88/88 (11 new: URL parsing, links, labels, KPI wording incl. a loss, CSV guard).
- Playwright 72/72, twice: sell → today's report, sort announced via `aria-sort`, chart table
  view, CSV download contents, invalid custom range explained, cashier blocked (page and export
  403), axe on `/reports` in both themes.
- Manual: 1440px light, 390px dark, cashier; no horizontal overflow, no console errors.

### Found and fixed
- On phones the preset bar widened the whole page by 197px: a grid item's minimum width follows
  its content. `min-w-0` on the filter row lets the presets scroll inside their own bar.
- Gross profit can be negative; the first KPI code dropped the sign. Added `signedCents`, and
  "% change" is now measured against the size of the earlier value.
- The Next.js dev server served a stale module after an edit (file watching on OneDrive). Restarting
  `npm run dev:web` fixed it.

### Known issues / open items
- Category is today's category, not the one at the time of sale.
- No refunds or voids yet, so the report shows gross sales only.
- One report request per view; very large stores may want caching later.

---

## 2026-11-22 — Suppliers and purchase orders (`feature/suppliers-purchase-orders`, based on `fix/hide-cost-from-cashiers`)

### Decisions (owner)
- Only the owner approves purchase orders; managers draft and receive.
- Receiving sets the product's cost to the order's unit cost (latest cost).
- Partial deliveries are supported, and an order can be closed short.
- The Overview's "Create purchase order" drafts an order from the reorder suggestions.

### Built
- Migration 5: `suppliers` (unique name per store, ignoring case), `purchase_orders`,
  `purchase_order_lines` (name/SKU/unit snapshots), `purchase_order_receipts` (one per delivery),
  `organizations.last_po_number`, `stock_movements.purchase_order_receipt_id`.
- API: `/suppliers` (list/search, create, edit, archive) and `/purchase-orders` (list by status,
  create, `from-reorder`, edit draft, approve, receive, close, cancel). Statuses: draft, approved,
  partially received, received, closed, cancelled. History records who did what and when.
- The reorder rule moved into `reorder_candidates`, shared by the Overview and `from-reorder`.
- Web: Suppliers (list, add, edit, archive), Purchase orders (status tabs, draft editor with product
  search and live totals, order page with role-aware actions, delivery form, deliveries, history),
  a "Purchase orders" nav item, and the Overview button now works.
- Shared pieces: `lib/form-state.ts` (moved out of the products actions), `ConfirmActionButton`,
  date formatters in `lib/format.ts`, `basePath` on `Pagination`.

### Verified
- pytest 92/92 (23 new). Includes: numbering per store, default costs, repeated/archived/foreign
  products, draft edit replacing lines, idempotent create, owner-only approval, archived supplier,
  partial then full delivery (stock, latest cost, ledger rows), over-receiving, retried delivery
  applied once, **4 concurrent deliveries of 6 on an order of 10 → exactly one succeeds**, close
  short, cancel rules, from-reorder, status filters, cashier 403, store isolation. Ruff clean.
- Vitest 77/77 (11 new: action rules per role and status, approval blockers, totals in centavos).
- Playwright 65/65, twice: supplier and product setup, draft → approve → short delivery → rest,
  stock and cost on the product page, Overview → draft → cancel, status tabs, cashier blocked, axe
  on the new pages (light and dark) and on an order page.
- Manual: the full flow as manager and owner at 1440px; editor and order page at 390px dark, no
  horizontal overflow, no console errors.

### Found and fixed
- The case-insensitive supplier index was generated as `lower('name')` (a constant), which would
  have allowed one supplier per store. Now `lower(name)`; checked in Postgres.
- A draft cancelled before choosing a supplier broke the "supplier required" CHECK; cancelled
  orders are now allowed without one.
- Lines within one delivery were listed in random order (same timestamp); now in the order's line order.
- axe: the product search's `aria-controls` pointed at a results list that wasn't rendered.

### Known issues / open items
- No PDF or email of a purchase order to send the supplier yet; it's a record inside Tindawise.
- Archived suppliers can't be shown or restored from the UI yet.
- The order page shows the ordered total; after closing short there is no "received value" line.
- The PO editor reuses the checkout's product search route (`/sell/products`).
- Dev API on Windows: the auto-reloader hung three times in this session. Workaround: run
  `uvicorn app.main:app --port 8000` without `--reload` and restart after API changes.

---

## 2026-11-22 — Fix: cashiers could see product costs (`fix/hide-cost-from-cashiers`)

### What happened
`GET /products`, `/products/{id}` and `/products/lookup` returned `cost` to every role. Cashiers saw
"Cost" and "Margin per unit" on product pages, and the POS search passed costs to their browser.
The Overview (previous entry) already hid costs, so the two disagreed.

### Fix
- One rule, `can_see_costs` in `api/deps.py` (owners and managers), used by products and Overview.
- Product reads return `cost: null` for cashiers. Writes are owner/manager-only, so they're unchanged.
- Web: `Product.cost` is `string | null`; the product page leaves out Cost and Margin when it's null.

### Verified
- pytest 69/69 (2 new: cashiers get `null` from list, search, detail and lookup; owners and
  managers get the cost). Ruff clean.
- Vitest 66/66, typecheck and ESLint clean. Playwright 52/52 (cashier product page shows no cost or
  margin; the owner's product test still checks the margin).
- Live API: cashier `cost = null`, owner `cost = 20.00`.

### Notes
- The dev API's reload hung again after switching branches (git rewrites many files at once). Also
  seen: stopping the `npm run dev:api` terminal on Windows can leave uvicorn running; stop the
  `python` processes holding :8000.

---

## 2026-11-22 — Real Overview (`feature/real-overview`)

### Built
- API: `GET /api/v1/overview`: today's sales, transactions and gross margin vs the same weekday
  last week; Sunday–Saturday sales by day; stock to watch; rule-based reorder quantities.
- `organizations.timezone` (migration 4, default `Asia/Manila`): days are the store's local days.
- Role rules in the API: cashiers get their own sales only and every cost field as `null`.
- Web `/`: real data behind Suspense with a skeleton and an "API not reachable" state. The KPI
  strip, chart and stock table are unchanged in layout. The chart lost its forecast line (no model
  yet) and its Y-axis now scales to the data. The AI Resibo card is replaced on this page by a plain
  "Reorder suggestions" panel that states it is a rule, not a forecast (owner's choice).
- `lib/overview.ts`: KPI wording, comparisons and chart rows as pure, unit-tested functions.
- `tzdata` declared as an API dependency (Windows has no built-in time zone database).

### Verified
- pytest 67/67 (9 new: local-day boundary at midnight Manila vs UTC, future days null not 0,
  margin, cashier scope and hidden costs, manager view, stock ordering and counts, reorder rule,
  archived products ignored, organization isolation, sign-in required). Ruff clean.
- Vitest 66/66 (16 new), typecheck and ESLint clean.
- Playwright 52/52, twice: real figures instead of "Sample data" for the owner, the cashier view
  (own sales, no margin or cost, no ordering button), and axe on `/`.
- Manual: screenshots as owner and cashier at 1440px and owner at 390px in dark mode; no console errors.

### Found and fixed
- Chart: with one day of sales this week, the line was a single point and drew nothing. This
  week's days now have dots.
- Flaky e2e test (from `feature/pos`): "an e-wallet sale needs a reference number" clicked the
  E-wallet radio with `force` right after scanning. Payment stays disabled for about 40 ms until the
  lookup adds the item, and `force` skips Playwright's enabled check, so the click could be lost.
  It failed 3 runs out of 3 here. The test now waits for the cart first. The app itself was correct.
- The dev API's auto-reload hung again on Windows: an old worker process kept the port and served
  the old code (the new route returned 404). The fix from `feature/pos` (watch only `app/`) did not
  cover this case: switching branches changes many files at once. Stopping the leftover worker
  process fixed it. Still open (below).
- `.next` locked by OneDrive during `npm run build` again; cleared the build output and rebuilt.

### Known issues / open items
- Gross margin is only as good as product costs: products saved with cost 0 overstate it.
- Reorder quantities are a simple rule (2 × reorder level or 14 days of sales). Demand forecasting
  replaces it in the ML phase.
- No way to change a store's time zone in the UI yet (default `Asia/Manila`).
- ~~The products API still returns `cost` to cashiers~~: fixed in `fix/hide-cost-from-cashiers`.
- Windows dev server: after many files change at once, uvicorn's reloader can leave an orphaned
  worker on :8000. Workaround: stop the leftover `python` process holding the port.
- The Next.js dev badge covers the sidebar's "Dark mode" button in development only.

---

## 2026-11-22 — Point of Sale (`feature/pos`)

### Built
- API: `sales` and `sale_lines` tables, per-store receipt counter, `stock_movements.sale_id`
  (migration 3); `POST/GET /sales`, `GET /sales/{id}`, `GET /products/lookup?code=`.
- Web `/sell`: scan (Enter = exact barcode/SKU) or search, cart with quantity steppers and stock
  limits, cash with quick amounts and live change, e-wallet with reference, receipt with print
  layout, phone layout with a sticky total bar.
- `lib/money.ts`: cart math in integer centavos.
- `npm run dev:api` now reloads only on changes in `app/`.

### Verified
- pytest 58/58 (14 new: totals from DB prices, merged duplicate scans, all-or-nothing on short
  stock, cash rule, e-wallet reference, idempotent retry, per-store receipt sequence, audit links,
  cashier visibility, isolation, lookup, 8 concurrent checkouts with no oversell or deadlock).
- Vitest 50/50, Playwright 51/51 (twice), including a cashier's full checkout and the stock drop,
  short cash, e-wallet, unknown barcode, out-of-stock, and axe on `/sell`.
- Web build passes without environment variables.

### Found and fixed
- The dev API watched `.venv`; pytest writes there, so reloads hung on Windows and old code kept
  serving (the cause of the earlier "orphaned worker" problem). Reload now watches `app/` only.
- `.next` folder locked during builds (OneDrive sync on Windows); cleared and rebuilt.

### Known issues / open items
- No VAT, discounts, refunds/voids, or offline mode yet. Overview still shows sample data even though
  real sales now exist (next: real Overview).

---

## 2026-11-22 — Sign-in, sessions and roles (`feature/auth-roles`)

### Built
- API: users, memberships (owner/manager/cashier) and sessions tables (migration 2); sign-up,
  sign-in, sign-out, `/auth/me`; team endpoints (owner only); role checks on every write endpoint;
  stock movements record who made them.
- Removed the temporary `X-Organization-Id` header everywhere: the organization now comes from the session.
- Web: `/login` and `/signup`, httpOnly session cookie, `proxy.ts` redirect for signed-out visitors,
  top bar with the real store name and an account menu (Team, Sign out), role-aware Products pages,
  and a Team page where owners add managers and cashiers.
- Seed: demo owner, manager and cashier accounts (local/CI only, public password).

### Verified
- pytest 44/44 (17 new: hashing, uniform login errors, expiry, revocation, roles, team, audit).
- Vitest 35/35, Playwright 44/44 (twice), including sign-in redirect, wrong password, sign-up,
  sign-out, cashier restrictions, team flow, and axe on `/login`, `/signup`, `/settings/team`.
- Web build passes without any environment variables.

### Bugs found and fixed
- axe: the account button showed "NS" but was named "Account: …" (WCAG 2.5.3 Label in Name).
  The name now starts with the initials.
- A test matched Next.js's own route announcer (`role="alert"`); scoped to `<main>`.
- Local only: an orphaned uvicorn worker kept serving old code on port 8000 (documented).

### Known issues / open items
- No sign-in rate limiting, password reset, email verification, or store switching yet.

---

## 2026-11-22 — Fix: CI build failed without API settings (`fix/ci-build-without-env`)

### What happened
The first CI run on `main` failed in the web build. `/products/new` loads categories without
reading the URL, so Next.js tried to prerender it, and `apiFetch` threw because `API_URL` wasn't
set. It passed locally only because `.env.local` existed. The API job passed; e2e was skipped.

### Fix
- `apiFetch` now calls `await connection()` first, which tells Next.js that API data is per-request.
  Prerendering stops there and the Suspense fallback goes into the static shell, so the build no
  longer needs the API or its settings.
- CI keeps building without `API_URL`, which now guards against this regression.
- GitHub Actions bumped to v7 (checkout, setup-node, setup-python, upload-artifact), which run on
  Node 24, removing the Node 20 deprecation warning.

### Verified
- Local build with `.env.local` removed: passes (reproduced the failure first).
- Vitest 23/23, Playwright 26/26, typecheck and lint clean.
- **The CI e2e job has never run yet** (it was skipped). It runs for the first time on this PR.

---

## 2026-11-22 — Testing and CI (`chore/testing-ci`, based on `feature/products-ui`)

### Built
- Vitest + Testing Library: 23 unit/component tests (formatters, URL guards, API client, components).
- Playwright: 26 end-to-end tests on desktop and a Pixel 7 profile, including the full product
  lifecycle against the real API, form errors, filters, navigation, the mobile drawer, and axe-core
  WCAG 2.2 AA checks in light and dark mode.
- GitHub Actions CI with web, api and e2e jobs.
- Root scripts: `test:web`, `test:e2e`, `test:api`, `lint:api` (cross-platform `scripts/api.mjs`).
- Root `README.md`.

### Verified (locally, Windows)
- Vitest 23/23, Playwright 26/26 (run twice, no flakes), pytest 27/27, Ruff, ESLint, TypeScript, build.
- **Not yet verified:** the CI workflow itself. It runs for the first time when this branch is pushed.

### Bugs found by the new tests
- **Contrast:** the shadcn `destructive` button (red on light red) measured 4.38:1. Now red text on the
  card surface (5.4:1).
- **Duplicate ids:** hidden pages kept by Cache Components could duplicate fixed ids like `quantity`,
  so a label could point at a hidden input. Switched to `useId()`.
- **Stale search box:** after archiving and returning to `/products`, the box still showed the old
  query while the list was unfiltered. It now resyncs from the URL.
- **Stale form values:** "Add product" kept the previous product's values after a create. The form
  now resets when hidden.

### Known issues / open items
- E2E runs locally against the development database and leaves archived `E2E test product …` rows.
- axe-core finds a subset of accessibility problems; a manual screen-reader pass is still needed.

---

## 2026-11-22 — Products UI (`feature/products-ui`, based on `feature/api-foundation`)

### Built
- Server-only API client (`lib/api`) with typed errors (`ApiError`, `ApiUnavailableError`).
- `/products`: search (debounced), stock-status and category filters, sorting, pagination, empty
  and "no matches" states, API-unreachable state with retry.
- `/products/new` and `/products/[id]/edit`: one form with field-level API errors, an error
  summary that receives focus, and preserved input after errors.
- `/products/[id]`: stock on hand, stock adjustment form (reason-aware add/remove, idempotency key),
  stock history, details with margin, archive with confirmation.
- `npm run dev:api` (cross-platform script) and `apps/web/.env.example`.

### Verified
- `typecheck`, `lint`, `build` pass. Products routes build as Partial Prerenders.
- Manually against the seeded API: list, filters, detail and form render; screenshots reviewed at
  1440px, 1024px and 390px.
- API tests: 27 passed (new: a blank `Idempotency-Key` is treated as no key).

### Bugs found and fixed
- Build failed: `usePathname` in the sidebar suspends on dynamic routes under Cache Components.
  Wrapped the nav in Suspense with a non-highlighted fallback.
- A blank `Idempotency-Key` would have been stored as `""` and collided across requests.
- Form fields without hint text were stretched by CSS grid and misaligned with their neighbours.
- Phones hid the stock status column entirely; the badge now shows under the product name.

### Known issues / open items
- Create, edit, adjust and archive are not yet covered by automated browser tests (next: Playwright).
- The Overview page still uses sample data.

---

## 2026-11-22 — API foundation (`feature/api-foundation`)

### Built
- `infrastructure/docker-compose.yml`: PostgreSQL 17 + pgvector on host port 5433, plus a separate
  `tindawise_test` database.
- `services/api`: FastAPI + SQLAlchemy 2.1 + Alembic + Pydantic v2 on Python 3.13.
- Tables: organizations, categories, products, stock_movements (first Alembic migration).
- Endpoints for categories, products (list/search/filter/sort/paginate, create, update, archive),
  stock adjustments with idempotency keys, and stock history.
- `scripts/seed.py`: a sample store with 17 sample products (barcodes in the GS1 internal "20" range,
  so they can't match real products).

### Verified
- `pytest`: 26 passed against real PostgreSQL. This includes 10 concurrent sales on 5 units
  (exactly 5 succeed), concurrent retries with one idempotency key (applied once), organization
  isolation, duplicate SKU/barcode, and decimal money.
- `ruff check` and `ruff format --check`: clean.
- Manual: `/health`, the filtered product list and `/docs` respond on the seeded database.

### Bugs found by tests
- `SELECT … FOR UPDATE` failed because the product query eagerly LEFT JOINs its category.
  Fixed by locking only the product row (`FOR UPDATE OF products`).
- The seed script inserted categories before their organization (no ORM relationship to order them).
  Fixed with an explicit flush.

### Known issues / open items
- No authentication. The development `X-Organization-Id` header is refused in production.
- Starlette deprecated `httpx` for its TestClient; switched to its successor `httpx2` (by the httpx author, maintained by Pydantic).

---

## 2026-11-22 — Web foundation (`feature/web-foundation`)

### Built
- Git repository, `.gitignore`, `.gitattributes` (LF line endings).
- npm workspaces monorepo root (`apps/*`, `packages/*`).
- `apps/web`: Next.js 16.4 + TypeScript strict + Tailwind v4 + ESLint + shadcn/ui (Radix) + Recharts 3.
- Design tokens from `design-system/tindawise-ai/MASTER.md` v0.1 applied in `globals.css` (light + dark).
- App shell: desktop sidebar, mobile drawer, top bar, skip link, theme toggle.
- Overview page (on **sample data**): KPI strip, weekly sales chart with table view, stock-to-watch table,
  Resibo AI reorder card.
- Placeholder pages for Sell, Products, Inventory, Suppliers and Reports, marked as planned.

### Verified
- `npm run typecheck` — pass.
- `npm run lint` — pass, no warnings.
- `npm run build` — pass. All 7 routes prerendered as static.
- Screenshots at 1440px (light + dark) and 390px (dark) reviewed with headless Chrome.

### Known issues / open items
- `npm audit`: 4 moderate findings in `minimatch`, pulled in by the **shadcn CLI** (dev dependency, via
  `ts-morph`). Nothing ships to the browser. The suggested fix downgrades shadcn to 1.0, so it is not applied.
- Global search is a disabled placeholder until the API exists.
- No automated UI tests yet (Vitest + Playwright are planned).
- Not tested yet: keyboard walkthrough on a real device, screen readers, Filipino-language string lengths.

### Next
- Products module UI (list, add/edit form) against typed sample data, or start `services/api`.

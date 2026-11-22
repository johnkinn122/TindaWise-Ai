# Development Log

Newest entries first. Each entry records what was built, how it was verified, and what is still open.

---

## 2026-11-23 — Fix: times shown in the store's time zone (`fix/store-timezone-display`)

### What was wrong
Every displayed time used Manila time (`lib/format.ts`, the POS receipt and the product stock
history each had `timeZone: "Asia/Manila"`). Once Store settings made the time zone editable,
a store in another zone would see its figures grouped by its own days but every time shifted.
I found this while building the activity log.

### Fix
- `/auth/me` returns `organization.timezone`.
- `formatDate(iso, timeZone)` and `formatDateTime(iso, timeZone)` require the zone, with one
  cached `Intl.DateTimeFormat` per style and zone. Making the argument required let the
  compiler list every call site (11 calls in 7 files); each now passes the store's zone, as a
  prop for the sales, ledger, purchase order and stock history tables and the POS receipt.
- No `"Asia/Manila"` is left in the app code. Calendar-date formatters stay in UTC by design.

### Verified
- API pytest 232/232 (1 new: `/auth/me` carries the zone and follows a change).
- Vitest 128/128 (2 new: one moment shown in Manila, Honolulu, London and New York; cached
  formatters don't mix zones).
- Playwright 94/94 (1 new): the store switches to Honolulu, then back to Manila, and the same
  activity entry is shown exactly 18 hours apart. A `finally` block restores Manila.

---

## 2026-11-23 — Audit log (`feature/audit-log`)

### Why
CLAUDE.md §13: keep audit logs for sensitive business operations. The AI agent phase will also
need somewhere trustworthy to record its proposals and the approvals.

### Built
- Migration `3f31c2367a78`: the `audit_events` table (actor, action, record, summary, JSON
  details) with an index on (organization, time). A trigger rejects every UPDATE and DELETE.
- `services/audit.py`: `record()` adds an event to the caller's transaction; `list_events()`
  reads them with filters.
- Eight actions are recorded, each just before the service's own commit: store settings changed,
  team member added, refund given, purchase order approved, cancelled or closed short, price or
  cost changed, active product archived.
- `GET /api/v1/audit-events` (owner only, new `CanReviewAudit`): filters for action, person and
  store days, newest first, paginated.
- Products, store settings and adding a member now pass the acting user (`actor_id`) to the
  service. The ledger's store-day helper is public as `store_day_range` and shared.
- Web `/settings/activity` ("Activity log" in the owner's account menu): a type filter (GET form),
  a table of when / what / who, and a link to the record (receipt, order, product, team,
  settings). On phones, the person goes under the summary. Cashiers and managers see a notice.

### Verified
- API pytest 231/231 (17 new):
  - Each action is recorded once, with the right actor, record, summary and details.
  - A refund retried with the same key is logged once.
  - Refused actions (over-refund, approving without a supplier) and no-op changes (same
    settings, same price, archiving twice) record nothing. Sales, stock adjustments and new
    suppliers aren't logged.
  - The database refuses UPDATE and DELETE, including raw SQL.
  - Newest first, filters, pages, store-day range, end before start 422, owner only (manager and
    cashier 403, signed-out 401), store isolation, and a manager's change attributed to the
    manager.
- Migration upgrade → downgrade → upgrade; `alembic check` clean.
- Vitest 126/126 (5 new: URL parsing, API query, links to records, labels for every action).
- Playwright 93/93 (3 new: the owner changes a setting and finds it in the log, filtered by
  type, with a link to the record; cashier notice and no menu entry; axe on `/settings/activity`
  in both themes). After a layout tweak, the affected specs passed again (45/45).
- Manual: 390px dark and 1440px light with real entries, no overflow, no console errors. On
  phones the date column was taking half the width, so it now wraps.

### Known issues / open items
- **Times show in Manila time everywhere** (`lib/format.ts` uses a fixed zone), even after a store
  changes its time zone in Store settings. The figures use the store's zone; only the displayed
  times don't. This came with store settings and should be fixed across the app.
- Not logged yet: sign-in failures, supplier changes, product edits other than price and cost.
- The log has no export, and there is no retention rule yet (CLAUDE.md §13 mentions retention).

---

## 2026-11-23 — Store settings (`feature/store-settings`)

### Decisions
- Owner's choice: a store settings page first, before anomaly detection or the copilot.
- Fields (the owner left this to me):
  - Store name: editable.
  - Default delivery time: editable. It closes the gap from the reorder PR.
  - Time zone: editable, with a warning. It decides where "today" starts, and a store abroad or
    set up with the wrong zone needs to fix it.
  - Currency: read-only. Every price and receipt is stored in it, and conversion rules don't
    exist.
  - The owner edits; managers view; cashiers get a notice.

### Built
- API `GET /api/v1/store` (owners and managers) and `PATCH /api/v1/store` (owner, new
  `CanEditStore`). Partial updates. The time zone is checked against `tzdata`, and the error
  suggests an example. No migration: the columns already exist.
- Web `/settings/store`: a form for the owner (name, a time zone select labelled with UTC
  offsets, default delivery time, currency shown read-only); details for managers; a notice for
  cashiers. A "Store settings" entry in the account menu for owners and managers. After saving,
  the top bar shows the new name without a reload.
- `lib/time-zones.ts`: zone options with offsets. The saved zone is always included, even when
  the browser's list doesn't have it.

### Verified
- API pytest 214/214 (10 new): read, partial update with trimming, nulls and an empty body
  change nothing, field errors (blank or long name, unknown zone, `Factory`, 61, −1), currency
  can't be changed, manager 403 on PATCH, cashier and signed-out refused, each owner changes only
  their own store, **the time zone moves where the Overview's week starts** (23:30 UTC Saturday
  is Sunday in Manila and still Saturday in Honolulu), and **the default delivery time reaches
  reorder suggestions**.
- Vitest 121/121 (3 new: offsets including daylight saving and half-hour zones, sorted list, the
  saved zone always present).
- Playwright 90/90 (3 new: the owner flow from the account menu, with a field error, save, the
  top bar updating, a reload, and the original values restored; cashier notice and no menu
  entry; axe on `/settings/store` in both themes).
- Manual: 390px dark and 1440px light, no horizontal overflow, no console errors.

### Found and fixed
- Node writes UTC's offset as "GMT+0", and other runtimes write "GMT". The unit test accepts
  both.

### Known issues / open items
- No audit log of settings changes yet (CLAUDE.md §13 asks for one for sensitive operations).
- The time zone list is long (about 400 entries) and has no search.

---

## 2026-11-23 — Reorder suggestions from recent sales and delivery time (`feature/forecast-reorder`)

### Decisions (owner)
- Lead times are set per supplier, with a store-wide default.
- The new rule replaces the Overview's suggestions, and each line explains why it's there.

### Decisions (mine)
- Daily rate = average over **in-stock days** only, so an empty shelf doesn't read as "no
  demand". I simulated it before building on it: it beat the plain average on all six datasets
  (EXPERIMENTS.md).
- Open purchase orders count as stock (position = on hand + undelivered). A draft made from
  the suggestions therefore stops them being suggested twice. The old rule ignored open orders.
- Fewer than 7 in-stock days → reorder-level fallback (new products, and the freshly seeded
  demo store). This is a judgment call, not simulated.
- Kept the plain panel, not the Resibo card: an average with a buffer isn't AI output (MASTER.md §7).

### Built
- Migration `709bf783c702`: `suppliers.lead_time_days` (nullable, 0-60) and
  `organizations.default_lead_time_days` (default 3, 0-60), each with a CHECK.
- API `app/services/reorder.py`: the rule (formulas in ARCHITECTURE "Reorder suggestions"),
  using the demand table from `demand_history.py`. The Overview and "create purchase order from
  suggestions" both call it. The old rule (`suggested_quantity`, 14-day recent sales) is removed.
- Overview `reorder` response: lines carry `on_order`, `basis`, `daily_rate`, `in_stock_days`,
  `lead_time_days`, `lead_time_source`, `supplier_name`, and the response gives `window_days`
  and `cover_days` (`sold_recently` and `lookback_days` are gone).
- Suppliers: `lead_time_days` in the API, a "Delivery time (days)" field on the form, and a
  "Delivery" column on the list (wide screens).
- Web reorder card: one line per product saying why ("3 on hand · 5 on order · about 2.5 sold a
  day · 2-day delivery from Weekly truck"), a footer that explains the rule, and a link to set
  delivery times.
- ML: `in_stock_moving_average` and its policy row in `python -m tindawise_ml policies`.

### Verified
- API pytest 204/204 (183 before; 23 new, 2 tests of the old rule removed). The rule's arithmetic: reorder point, cover, buffer, rounding,
  open orders, fallback, quiet products, same-day delivery. Against real records: rate from
  in-stock days (13 days at 4 a day, not 28 at 2), supplier lead time and name, latest supplier
  wins, cancelled orders ignored, only the undelivered part of a partly received order, store
  default, new products, most urgent first, archived and other stores left out, damage
  counts as a stockout day, the Overview shape, a draft stopping repeat suggestions. Supplier
  lead time optional, editable, 0-60 only.
- Mutation check: 4 deliberate bugs in the rule. "Oldest supplier instead of latest" survived,
  so I added the switched-supplier test, which catches it.
- Migration: upgrade → downgrade → upgrade on the dev database, `alembic check` clean, CHECK
  rejects 61. (Fixed: the downgrade first used names the naming convention prefixed twice.)
- Web: typecheck, ESLint, Vitest 118/118 (4 new for the reason line). Playwright: see below.
- ML pytest 102/102.

### Known issues / open items
- The store default (3 days) can only be changed in the database. There is no store settings
  page yet.
- Products have no direct supplier link. The lead time comes from the latest purchase order's
  supplier.
- Refunds no longer lower the rate (the old rule subtracted them). This is the same as the
  demand table.

---

## 2026-11-23 — ML: reorder policy simulation (`feature/ml-reorder-policy`)

### Built
- `tindawise_ml/inventory.py`: a day-by-day replay (morning deliveries → sales capped by the
  shelf → evening orders arriving 1-3 days later). Every policy faces the same true demand and
  the same delivery-delay draws, and sees only sales and stockout flags up to today
  (including its own results). Reports fill rate, lost units, stockout days, days of stock
  and orders.
- Policies: `CurrentRule` (the app's Overview rule, same formula) and `ForecastPolicy` (reorder
  point = forecast lead-time demand + buffer; order up to lead + cover days; weekly forecast
  refresh), with any forecaster.
- `python -m tindawise_ml policies` / `npm run policies:ml`: the current rule vs moving-average
  and LightGBM policies at cover 7/10/14 × safety 0/1.

### Results (synthetic; full tables in `docs/ml/EXPERIMENTS.md`)
- At about the same orders and stock as the current rule (cover 10, safety 1), forecast-based
  ordering lost **42-63% fewer units** on all six datasets tried, with 3-10% more orders.
- The moving average and LightGBM tied inside the policy (3 wins each). The improvement comes
  from the policy, not the forecaster.
- All 13 settings are reported. Cover 10 was chosen for the like-for-like comparison because
  its orders and stock match the current rule.

### Verified
- ML pytest 102/102 (17 new): the app rule's formula and threshold, forecast policy reorder
  point and quantity, buffer from in-stock days only, weekly refresh, horizon, conservation
  (closing = previous + deliveries due − sales), sales ≤ demand and shelf, no reorder before the
  delivery arrives, policies see today but not tomorrow and see their own sales, same inputs →
  same outcome, never-ordering empties shelves, summary math, real data refused, CLI.
- Mutation check: 3 deliberate simulator bugs. Two were caught at first. "Deliveries arrive a
  day late" survived, so I added the conservation test, which catches it.
- Ruff clean. The baseline and LightGBM numbers in EXPERIMENTS are unchanged.

### Found and fixed
- My first "no reorder while on order" test assumed orders can't be placed on consecutive days.
  They can, when a 1-day delivery arrived in between. The test now checks the exact rule using
  the recorded delivery delays.

### Known issues / open items
- Synthetic only: true demand is needed to count lost sales.
- Lead times are assumed (1-3 days, uniform). The app doesn't record them yet.
- I didn't search for a better fixed rule. Nothing is priced (orders, stock, lost sales).
- The `policies` command takes about 3 minutes with LightGBM, so it's not in CI; the tests cover
  the simulator.

---

## 2026-11-22 — ML: demand table from the database + sample history store (`feature/ml-real-data`)

### Decisions (owner)
- The API service builds the table from the database (it owns the schema, time zones and
  isolation), and ML reads an exported CSV. The ML package stays free of database code.
- An opt-in script writes synthetic history into the database for an end-to-end check.

### Decision (mine, explained in the PR)
- The sample history goes into a **separate sample store**, not the demo store. The demo
  products' ledgers already begin with their opening stock, so two years written before it
  would break the `balance_after` chain. Also, Playwright runs against the demo store locally.

### Built
- API `app/services/demand_history.py` → `daily_demand(db, org, start, end)`: one row per
  active product per store day. `units_sold` from `sale_lines` (refunds not subtracted).
  `stockout` from the ledger (a movement ended at 0, or the carried balance was 0). Days
  before a product existed count as stockouts. Uses three grouped queries plus a zero-fill.
- `scripts/export_demand.py`: writes the contract CSV (default range: first product day to
  yesterday).
- `scripts/seed_sample_history.py` (opt-in, refused in production, refuses an existing sample
  store): creates "Sample history store (synthetic)" with `sample-owner@example.com` and writes
  the history as opening stock, morning deliveries, and receipts of 1-4 units spread over
  08:00-20:00. Receipts are 25% e-wallet and 75% cash rounded up to ₱20, with one sale
  movement per line. Bulk inserts; checks that the history replays without going negative and
  ends before today.
- ML: `generate` also writes `received` and `closing_stock`. `--end` sets the last day.
  `load_demand_csv` reads and validates exported CSVs. `backtest/tune --csv` run on them (no
  oracle row for real data).
- `.gitignore`: `services/**/*.csv` (exports are business data).

### Verified
- API pytest 183/183 (29 new). Loader: store-day boundary (23:30 vs 00:30 Manila), zero-fill and
  order, stockout until restocked, restocked the same day carries the *last* balance, damage
  empties the shelf, balance carried in from before the range, product created mid-range,
  never-stocked product, refunds don't reduce units, archived excluded, other store's sales and
  stock never count, empty store, end before start. Seeder: database gives back the same
  table, ledger chain and `stock_on_hand` agree, receipts numbered with totals = Σ lines,
  same seed → same receipts, history checks, unknown SKUs. Export: CSV contents, defaults,
  errors.
- Mutation check on the loader: 4 deliberate bugs. 3 were caught at first. The 4th (reading a
  day's first balance instead of its last) survived, so I added the "restocked the same day"
  test, which catches it.
- ML pytest 85/85 (13 new): stock columns add up, history unchanged by the new columns, CSV round
  trip and contract errors, `--end`, `--start` with `--end` refused, backtest on a CSV.
- **End to end on the dev database:** generate → seed (21,667 receipts, about 4 minutes) →
  export (1 s) → 12,410 rows identical to the generated table, and identical backtest scores.
- Overview and Reports on the sample store: last week's daily sales show, and Reports takes
  0.06 s for 30 days and 0.13 s for a full year (11,125 receipts). Checked by calling the services
  directly. No screens changed, so I didn't do a visual check.
- Ruff clean in both services.

### Known issues / open items
- Seeding takes about 4 minutes (bulk inserts of about 120,000 rows). Fine for a one-off.
- Sample prices and costs stay at today's catalogue values for the whole history.
- A shelf that was empty overnight and restocked during the day isn't counted as a stockout.
- Two movements of one product with the same timestamp have no defined order. Checkout and
  refunds don't produce that today.
- The sample store is only reachable with its own login (no store switching yet).

---

## 2026-11-22 — ML: LightGBM forecaster (`feature/ml-lightgbm`)

### Built
- `features.py`: direct multi-horizon feature rows (origin, h, product) built from days up to
  the origin only. Recent means, std, same weekday in past weeks, an in-stock-only mean,
  stockout share, target-day calendar (weekday, day, payday, month). Stockout days are dropped
  as labels.
- `gbm.py`: one LightGBM model for all products (Poisson objective, deterministic settings),
  retrained at every origin. Native LightGBM API, so no scikit-learn dependency.
- `tuning.py` + `python -m tindawise_ml tune`: an 18-setting grid scored on the validation
  period (the 84 days before the test period) only.
- Backtest now also reports **bias** and **7-day totals per product**, and on synthetic data an
  **oracle floor** (true mean demand). `tiling_origins(before_days=…)` gives the validation period.
- Forecasters receive a `History` (sold + stockout tables) instead of the sold table alone.
  The baselines' numbers are unchanged (checked before and after).
- `npm run tune:ml`. `lightgbm>=4.5` added to `services/ml/pyproject.toml`.

### Results (synthetic data; full tables in `docs/ml/EXPERIMENTS.md`)
- Tuning: every setting landed between 49.7% and 50.6% daily WAPE on validation. The oracle
  floor is 49.6%, so daily scores barely separate methods on this data. Chose 7 leaves,
  min 200 per leaf, 300 rounds.
- Test period, run once (seed 42): LightGBM 7-day WAPE **20.8%** vs moving average 22.6%
  (oracle floor 20.0%); daily 49.7% vs 50.5%; bias −4.4% vs −6.1%.
- Same settings on seeds 1-5: LightGBM better on 7-day totals every time (by 1.4-2.6 points).
  Daily, it was better on 5 of 6; on seed 2 the moving average won by 0.3 points.

### Verified
- ML pytest 72/72 with warnings as errors (49 before). New: hand-checked feature values (windows,
  same-weekday lookbacks, calendar of the target day, in-stock mean around stockouts), stockout
  days never used as labels, labels never past the last known day, forecast shape/dates,
  same data → same forecast, learns a weekend pattern, **leakage test now includes LightGBM**
  (sales and stockout flags after the origin changed → identical forecasts), validation
  windows end before the test period, tuning never touches the test period, bias and 7-day
  totals hand-checked, oracle equals the generator's mean.
- A fresh virtual environment installed from `pyproject.toml` passes all 72.
- Ruff check and format clean.
- **Not yet verified:** the CI job with LightGBM on Linux. It runs on this branch's PR.

### Found and fixed
- pandas 3 deprecates `DatetimeIndex.weekday` (caught by `-W error`); now `day_of_week`.
- My first oracle helper guessed where the trend starts. `expected_demand` now takes an
  explicit `start`, and the oracle passes the history's first day. A test checks it.

### Known issues / open items
- Everything is still synthetic. The model's features match the generator's effects, which
  makes this data friendly to it.
- The model has seen only one December before the test period's December.
- Skipping stockout days biases scores toward under-forecasting a little (oracle bias +0.6% to +5.2%).
- Tuning takes about 3 minutes, so it is not in CI. CI runs the backtest (about 10 s).

---

## 2026-11-22 — ML: forecasting baselines on synthetic history (`feature/ml-baselines`)

First step of the machine learning phase (roadmap: Core Platform → **ML** → AI Agents → Deployment).

### Decision (owner)
- Start the ML phase now. Business settings, audit log and sign-in hardening come later.

### Built
- `services/ml`: a separate Python package (`tindawise_ml`, numpy + pandas only) with its own
  virtual environment. It doesn't import the API and the API doesn't import it.
- Daily demand table contract (`data.py`) with a validator: one zero-filled row per product per
  day, `units_sold`, `stockout`.
- Synthetic sample history (`synthetic.py`) for the 17 demo SKUs: seeded and repeatable,
  with assumed weekday, payday, month, hot-season, Christmas and trend effects, negative binomial
  noise, and a stock simulation whose stockouts cap sales (censored demand). Labelled as sample data
  in the module, the CLI output, and the docs.
- Baselines (`baselines.py`): naive, seasonal naive (7 days), 28-day moving average.
- Metrics (`metrics.py`): MAE, RMSE, WAPE. Rolling-origin backtest and scoring (`backtest.py`)
  that skips stockout days.
- CLI: `python -m tindawise_ml backtest | generate`. Root scripts `test:ml`, `lint:ml`,
  `backtest:ml`. The venv lookup moved from `scripts/api.mjs` into `scripts/python-venv.mjs`, shared
  by both (API script behaviour unchanged).
- CI job **ml**: Ruff, `pytest -W error`, and a backtest smoke run.
- Docs: `docs/ml/EXPERIMENTS.md` (results), ARCHITECTURE "Machine learning", `services/ml/README.md`.

### Results (synthetic data, seed 42, last 84 days, 7-day horizon)
- 28-day moving average WAPE **50.5%** (MAE 2.56, RMSE 3.89); naive 65.8%; seasonal naive 69.1%.
- The ranking held on seeds 1-5 (moving average 49.2-52.7%). Details and limits in EXPERIMENTS.md.
- These describe the made-up data only, not a real store.

### Verified
- ML pytest 49/49 with warnings as errors: metrics against hand-computed values; contract
  violations named; same seed → same table; each SKU's history independent of the others; sales
  ≤ demand and every shortfall flagged; stockout rate between 1% and 10%; documented demand effects
  reproduced exactly; origins tile the test period; **leakage test** (multiply every value after an
  origin by 10 → identical forecasts); the `demand` column is never read; stockout days skipped
  with hand-checked scores.
- `ruff check` and `ruff format --check` clean. `npm run test:ml`, `lint:ml`, `backtest:ml` run.
- Through the refactored script: `npm run lint:api` clean, `npm run test:api` 154/154. The first
  run errored on every test because Docker Desktop wasn't running. Started it and reran.
- **Not yet verified:** the new CI job. It runs for the first time on this branch's PR.

### Found and fixed
- A test assumed the trend was negligible across one week; at the tolerance used it wasn't. The
  test now includes the trend factor exactly instead of loosening the tolerance.

### Known issues / open items
- Only synthetic data. No loader for the real database yet.
- Baselines read stockout days as recorded, which biases them low after a stockout.
- Metrics treat over- and under-forecasting the same; ordering decisions don't.
- No trained model yet (LightGBM is next), and nothing is shown in the app.

---

## 2026-11-22 — Inventory page (`feature/inventory-page`)

### Decision (owner)
- Owners and managers only. Cashiers see a notice pointing to Products for stock levels.

### Built
- API `GET /api/v1/inventory/movements`: the store-wide ledger, newest first, paginated, filtered by
  reason, product search (name/SKU), product id, person and store-day range. Each row carries the
  product, who made it, and its source (sale, refund or purchase order) with its number.
- API `GET /api/v1/inventory/summary`: active products, units on hand, stock value at current cost,
  low and out-of-stock counts, and the people who have changed stock (for the filter).
- Migration `0524a3c9f00c`: index `(organization_id, created_at)` on `stock_movements`. No new tables.
- Web `/inventory` (replaces the "planned" placeholder): KPI strip, then a filter row (GET form; empty
  fields dropped from the URL by a redirect) above the ledger table with pagination. Source links
  open the receipt or purchase order; product names open the product. A one-product view has a
  removable chip. On phones, date, reason and source fold under the product name.
- Product page: "See all in Inventory" under Stock history (owners and managers).

### Verified
- pytest 154/154 (141 before), 13 in `test_inventory_ledger.py`: every movement kind with its
  source, filters (reason, product, search incl. literal `%` and `_`, person), store-day boundaries
  (00:30 Manila counts for that day), end-before-start 422, pages, summary figures with an
  archived product excluded, people list, cashier 403, signed-out 401, other store isolation.
- Vitest 114/114 (106 before): URL parsing (malformed values dropped), links, source labels,
  change signs, KPI wording.
- Playwright: 86 of 87 passed in the full run; the one failure was a mistake in the new cashier
  test (its text match also found the notice). Fixed it, and `cashier.spec.ts` then passed 10/10.
  New: sell → ledger search → receipt link; reason filter; product page → one-product ledger →
  remove chip; bad range explained; no-match empty state; cashier notice; phone fit; axe on
  `/inventory` in both themes and on the filtered view.
- `alembic upgrade` / `downgrade -1` / `upgrade` on the dev database; `alembic check` clean.
  Typecheck, ESLint and Ruff pass.
- Manual (running app, demo data): 1440px, 1280px, 1024px light; 390px dark; cashier. No horizontal
  overflow, no console errors.

### Found and fixed
- At 1024px the ledger widened the whole page by 52px (a grid item's minimum width follows its
  content). `min-w-0` on the section; the "By" column now shows from 1280px, and below that the
  name sits under the date.
- Sale, refund and delivery movements repeat their own number in the note ("Receipt S-000052");
  the note is shown only when there is no source link.
- The "who" filter first listed every member, including test cashiers who never changed stock. It
  now lists only people who appear in the ledger.
- Removed the navigation test for the "Inventory is planned" placeholder: no planned pages remain.
- The API dev server didn't reload after new files were added (OneDrive file watching). Restarting
  `npm run dev:api` fixed it.

### Known issues / open items
- Stock value uses current cost, not FIFO or average cost.
- No CSV export of the ledger yet.
- `PlannedModule` has no users now; kept for the planned ML and AI pages.
- The date fields use the browser's date picker, whose format follows the device's locale.

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

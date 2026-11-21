# Development Log

Newest entries first. Each entry records what was built, how it was verified, and what is still open.

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

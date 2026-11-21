# Development Log

Newest entries first. Each entry records what was built, how it was verified, and what is still open.

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

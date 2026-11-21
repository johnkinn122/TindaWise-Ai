# Tindawise AI — Architecture

> Status legend: ✅ built · 🚧 in progress · 📋 planned

## Repository layout

```
tindawise-ai/
├── apps/
│   └── web/                 ✅ Next.js frontend: app shell, Overview (sample data), Products (live API)
├── services/
│   ├── api/                 ✅ FastAPI backend: products, categories, inventory ledger
│   └── ml/                  📋 Forecasting + anomaly detection (scikit-learn, LightGBM)
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
│       ├── page.tsx            "/" Overview (sample data)
│       ├── error.tsx           Fallback error screen inside the shell
│       ├── products/           Live: list, /new, /[id] (detail + stock), /[id]/edit, actions.ts
│       └── sell|inventory|suppliers|reports/page.tsx   Planned-module placeholders
├── components/
│   ├── ui/                     shadcn primitives (button, table, sheet, badge, tooltip, separator)
│   ├── layout/                 App shell: sidebar, mobile drawer, top bar, nav, theme toggle
│   ├── dashboard/              Overview building blocks: KPI strip, chart, stock table, Resibo card
│   └── products/               Filters, table, pagination, product form, stock form, archive dialog
└── lib/
    ├── api/                    server-only API client + typed product endpoints
    ├── format.ts               Peso / number / percent formatting (en-PH)
    ├── sample-data.ts          SAMPLE DATA ONLY — replaced by API calls later
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
- **AI actions stay inert until approval exists.** The Resibo card's "Create purchase order" is disabled
  until the backend has a human-approval flow (claude.md §9).

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
│   └── v1/       auth.py, members.py, categories.py, products.py
├── services/     Business rules. Never imports FastAPI; raises domain errors.
│   ├── auth.py        sign-up, sign-in, sessions, team membership
│   ├── products.py    product + category rules, org-scoped queries
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
       └─< sessions (token hash only)    └─< stock_movements.created_by_user_id → users
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
- Windows: `uvicorn --reload` can leave an orphaned worker that keeps port 8000 open with old code.
  If new endpoints return 404, stop every `python … uvicorn` / `multiprocessing` process and restart.

## Testing and CI

| Level | Tool | Where | Covers |
|---|---|---|---|
| Unit / component | Vitest + Testing Library (jsdom) | `apps/web/test/unit` | formatters, URL guards, API client errors, components |
| API | pytest on real PostgreSQL | `services/api/tests` | rules, constraints, concurrency, idempotency, isolation |
| End-to-end | Playwright (Chromium, desktop + Pixel 7) | `apps/web/test/e2e` | product lifecycle, forms, filters, navigation, mobile drawer |
| Accessibility | axe-core in Playwright | `apps/web/test/e2e/accessibility.spec.ts` | WCAG 2.2 A/AA rules, light + dark |

`.github/workflows/ci.yml` runs three jobs on every PR: **web** (types, lint, unit, build),
**api** (Ruff, pytest with a PostgreSQL service), and **e2e** (needs both: migrates and seeds a
fresh database, then runs Playwright against the production build and the API).

### Cache Components and hidden pages

With Cache Components, Next.js keeps recently visited pages mounted but hidden (React `<Activity>`).
Consequences handled in the code:

- **Ids must be unique per instance.** Form fields and panels use `useId()`, so a hidden copy of a
  page can't steal a `<label for>` or `aria-labelledby` target.
- **State survives navigation.** The product form resets itself when hidden; the search box resyncs
  from the URL; the stock form doesn't replay an old "Stock updated" message.
- **Tests use `getByRole`**, which ignores hidden elements, instead of `getByLabel`.

## ML, agents

📋 Not started. See `claude.md` §7–§9.

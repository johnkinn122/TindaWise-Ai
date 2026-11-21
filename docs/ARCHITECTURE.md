# Tindawise AI — Architecture

> Status legend: ✅ built · 🚧 in progress · 📋 planned

## Repository layout

```
tindawise-ai/
├── apps/
│   └── web/                 ✅ Next.js frontend (UI shell + Overview on sample data)
├── services/
│   ├── api/                 📋 FastAPI backend (Pydantic, SQLAlchemy, Alembic)
│   └── ml/                  📋 Forecasting + anomaly detection (scikit-learn, LightGBM)
├── packages/                📋 Shared TypeScript types and UI used across apps
├── infrastructure/          📋 Docker, GitHub Actions, deployment config
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
│       ├── page.tsx            "/" Overview
│       └── sell|products|inventory|suppliers|reports/page.tsx   Planned-module placeholders
├── components/
│   ├── ui/                     shadcn primitives (button, table, sheet, badge, tooltip, separator)
│   ├── layout/                 App shell: sidebar, mobile drawer, top bar, nav, theme toggle
│   └── dashboard/              Overview building blocks: KPI strip, chart, stock table, Resibo card
└── lib/
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
- **AI actions stay inert until approval exists.** The Resibo card's "Create purchase order" is disabled
  until the backend has a human-approval flow (claude.md §9).

## Backend, ML, agents

📋 Not started. See `claude.md` §11–§13 for the planned structure and standards.

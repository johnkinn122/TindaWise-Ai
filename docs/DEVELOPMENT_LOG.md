# Development Log

Newest entries first. Each entry records what was built, how it was verified, and what is still open.

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

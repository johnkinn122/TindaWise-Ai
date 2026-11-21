# Tindawise AI — Design System (MASTER)

> Global source of truth. Page-specific overrides go in `pages/<page>.md` and win over this file.
> Status: **v0.1 — proposed, awaiting approval.** Nothing here is implemented in app code yet.

## 1. Design intent

- **Subject:** an operations tool for Filipino small and medium retailers — sari-sari stores, mini-marts, hardware shops, pharmacies.
- **Audience:** owners and staff who check stock, ring up sales, and reorder from suppliers, often on a laptop at the counter or a phone in the stockroom.
- **Primary job:** tell the owner, at a glance, *what is selling, what is running out, and what to do about it.*
- **Character:** calm, trustworthy, and local, like a well-kept store ledger. No glassmorphism, no gradient washes, no neon "AI" styling.
- **The one bold element:** the **Resibo card** (§7). AI insights are printed like a thermal-paper receipt strip. Everything else stays quiet so this stands out.

### Decisions made against the generic default

| Generic default (from the base recommendation) | Tindawise choice | Why |
|---|---|---|
| Trust blue `#2563EB` + orange CTA | Dahon green `#0F5C4D` + Mangga yellow `#F2B33D` | Green reads as money and growth. Mango is a warm local accent, used only for AI signals |
| Glassmorphism | Flat surfaces, 1px borders, almost no shadows | Blur hurts contrast on dense tables and costs performance on low-end laptops |
| Plus Jakarta Sans | Bricolage Grotesque (display) + IBM Plex Sans (UI) | Plex has ledger-like tabular figures. Bricolage gives page titles and big numbers a voice |
| Four identical KPI cards | One KPI strip split by dividers | Numbers read as one row of a ledger, not as four separate widgets |
| Landing-page pattern | App shell: sidebar + top bar + content | This is a working tool, not a marketing page |

## 2. Color tokens

Components use **semantic tokens only**, never raw hex.

### Light

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--background` | `#F6F7F5` | App canvas (cool off-white, not cream) | — |
| `--card` | `#FFFFFF` | Panels, tables, dialogs | — |
| `--foreground` | `#1A2420` | Primary text (green-tinted ink) | 14.8:1 on bg |
| `--muted-foreground` | `#5B6661` | Secondary text, captions | 5.5:1 on bg |
| `--muted` | `#EEF1EE` | Hover rows, subtle fills | — |
| `--border` | `#DDE2DE` | Dividers, input borders | — |
| `--primary` | `#0F5C4D` | **Dahon** — primary actions, active nav | 7.9:1 with white |
| `--primary-foreground` | `#FFFFFF` | Text on primary | — |
| `--accent` | `#F2B33D` | **Mangga** — AI insights and highlights only | ink text 8.6:1 |
| `--accent-foreground` | `#1A2420` | Text on Mangga (never white) | — |
| `--success` | `#1E7F4F` | In stock, completed | 5.0:1 |
| `--warning` | `#B45309` | Low stock, pending | 5.0:1 |
| `--destructive` | `#C2362B` | Out of stock, void, delete | 5.5:1 |
| `--info` | `#2F5DA8` | Neutral notices | 6.5:1 |
| `--ring` | `#0F5C4D` | Focus ring | — |

> ⚠️ Mangga `#F2B33D` is **never** used as text on white (it fails contrast). Use it only as a fill with ink text on top.

### Dark (designed together with light, not inverted)

| Token | Hex |
|---|---|
| `--background` | `#0F1513` |
| `--card` | `#161E1B` |
| `--foreground` | `#E6ECE9` (15.4:1) |
| `--muted-foreground` | `#9AA6A0` (6.8:1 on card) |
| `--muted` | `#1D2723` |
| `--border` | `#2A3530` |
| `--primary` | `#4FBFA3` (dark text `#0F1513` on top, 8.2:1) |
| `--accent` | `#F2B33D` |
| `--success` / `--warning` / `--destructive` / `--info` | `#4CC38A` / `#E8A04A` / `#F07065` / `#7FA6E8` |

### Chart palette (Recharts)

Fixed order. Every series must stay distinguishable by label or shape too, not by color alone.

| # | Light | Dark | Typical series |
|---|---|---|---|
| 1 | `#0F5C4D` | `#4FBFA3` | Sales / this period |
| 2 | `#2F5DA8` | `#7FA6E8` | Comparison / last period |
| 3 | `#B7791F` | `#E0A94A` | Forecast (dashed line) |
| 4 | `#7A4E8C` | `#B98ACB` | Category 4 |
| 5 | `#8A948F` | `#7D8A84` | Other / remainder |

Gridlines use `--border`. A forecast is always **dashed**, so it isn't confused with actuals.

## 3. Typography

| Role | Family | Weights | Notes |
|---|---|---|---|
| Display | **Bricolage Grotesque** | 600, 700 | Page titles, KPI values, empty-state headlines. Never for body text |
| UI / body | **IBM Plex Sans** | 400, 500, 600 | Everything else. Use `font-variant-numeric: tabular-nums` on all numbers |

Load both with `next/font/google` (`display: swap`).

### Scale (rem, 16px base)

| Token | Size / line-height | Family | Use |
|---|---|---|---|
| `text-display` | 2rem / 1.15 | Bricolage 700 | Page title |
| `text-kpi` | 1.75rem / 1.1 | Bricolage 600, tabular | KPI values |
| `text-title` | 1.125rem / 1.4 | Plex 600 | Panel titles |
| `text-body` | 0.9375rem / 1.55 | Plex 400 | Default UI text (15px; 16px on mobile inputs) |
| `text-small` | 0.8125rem / 1.5 | Plex 400/500 | Table cells, captions, helper text |
| `text-micro` | 0.75rem / 1.4 | Plex 500 | Badges, chart ticks. Minimum size |

Rules:
- Sentence case everywhere. **No ALL-CAPS labels or eyebrows.**
- Currency is always `₱1,234.50`. Format with `Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP' })`.
- Numbers in tables are right-aligned and tabular.

## 4. Spacing, radius, elevation

- **Spacing:** 4px base. Dense dashboard scale: `4, 8, 12, 16, 24, 32`. Panel padding is 16px (20px on ≥1280px).
- **Radius hierarchy** (deliberately not one value for everything):
  - `--radius-sm` 6px: inputs, buttons, badges
  - `--radius-md` 10px: panels, cards, dialogs
  - `--radius-full`: status pills, avatars
- **Elevation:** panels use a border, **no shadow**. Shadows only on floating layers (popover, dropdown, dialog): `0 8px 24px -8px rgb(15 21 19 / 0.18)`.
- **Z-index:** base 0 · sticky header 20 · sidebar overlay 30 · popover 40 · dialog 50 · toast 60.

## 5. Layout

```
┌──────────┬───────────────────────────────────────────────┐
│ Sidebar  │ Top bar: store switcher · search (Ctrl+K) · ⚙ │
│ 240px    ├───────────────────────────────────────────────┤
│ (64px    │ Page title                     [Primary CTA]  │
│ collapsed│ ┌───────────────────────────────────────────┐ │
│ )        │ │ KPI strip — one panel, divided            │ │
│          │ └───────────────────────────────────────────┘ │
│ Overview │ ┌──────────────────────────┐ ┌──────────────┐ │
│ Sell     │ │ Main chart / table (8col)│ │ Resibo (4col)│ │
│ Products │ └──────────────────────────┘ └──────────────┘ │
│ Inventory│                                               │
│ Suppliers│                                               │
│ Reports  │                                               │
└──────────┴───────────────────────────────────────────────┘
```

- Content is left-aligned, max width 1440px, 12-column grid, 24px gutter.
- Breakpoints: 375 / 768 / 1024 / 1440. Below 1024px the sidebar becomes a drawer, and the KPI strip wraps to 2×2.
- One primary CTA per page (e.g. "New sale", "Add product").
- Destructive actions (delete, void sale, sign out) are separated from normal actions.

## 6. Components (shadcn/ui base)

| Component | Rule |
|---|---|
| Button | Heights 36px (default) / 44px (POS + mobile). Variants: primary, secondary (outline), ghost, destructive |
| Input | Visible label above, helper/error text below, linked with `aria-describedby`. Validate on blur |
| Table | Sticky header, zebra-free, row hover `--muted`, numbers right-aligned, sortable headers with `aria-sort`. Virtualize at 50+ rows |
| Stock badge | Icon + text + color. Never color alone: `● In stock`, `▲ Low — 4 left`, `✕ Out of stock` |
| Empty state | Display-font headline + one sentence + one action ("Add your first product") |
| Toast | `aria-live="polite"`, auto-dismiss 4s, Undo for destructive actions |
| Icons | Lucide (shadcn default), 1.5px stroke, sizes 16/20/24. Decorative icons get `aria-hidden` |

## 7. Signature: the Resibo card

AI insights (demand forecasts, reorder suggestions, anomalies) appear as a receipt strip:

- White paper on `--card`, with a **zig-zag perforated bottom edge** (CSS `mask`).
- A Mangga `--accent` tab at the top labelled with the insight type ("Reorder suggestion").
- Line items are dotted-leader rows: `Lucky Me Pancit Canton ........ 48 pcs`.
- Footer: confidence ("Based on 90 days of sales") + actions `Create purchase order` / `Dismiss`.
- **Rule:** the Resibo style belongs to AI output only. Using it elsewhere dilutes the meaning.

## 8. Motion

- Subtle. Durations 120ms (hover/press) · 200ms (expand, dropdown) · 260ms (dialog/drawer enter), exits ~65% of enter.
- Animate `transform` and `opacity` only.
- One orchestrated moment: the Resibo card "prints" (slides down 8px + fades) when a new insight arrives. No scroll-reveal on dashboard panels.
- `prefers-reduced-motion: reduce` turns all of this off.

## 9. Accessibility floor

- Text contrast ≥ 4.5:1, UI boundaries ≥ 3:1 (verified for every token above).
- Visible 2px focus ring (`--ring`) with 2px offset on every interactive element.
- Skip link to main content, logical heading order, full keyboard support including the POS.
- Every chart has a text summary (`aria-label`) and a table view toggle.

## 10. Copy voice

- Plain English, sentence case, active verbs. The button says "Create purchase order", and the toast says "Purchase order created".
- Name things the way store owners do: "Products", "Stock", "Suppliers", not "SKUs" or "entities".
- Errors state the cause and the fix: "Barcode already used by *Coke 1.5L*. Scan a different item or edit that product."
- Planned: Filipino (Tagalog) language toggle. The layout must handle ~30% longer strings.

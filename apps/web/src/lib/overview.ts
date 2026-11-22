/**
 * Turns the API's Overview response into what the Overview components display.
 * Pure functions (no fetching), so the wording and comparisons are unit-tested.
 * Definitions of each figure live in services/api/app/services/overview.py.
 */

import type { Overview, StockStatus, StockWatchItem } from "@/lib/api/types";
import { formatNumber, formatPercent, formatPesoWhole } from "@/lib/format";
import { toCents } from "@/lib/money";

export interface Kpi {
  id: string;
  label: string;
  value: string;
  /** Short comparison line, e.g. "12% vs last Friday". */
  change: string;
  trend: "up" | "down" | "neutral";
}

export interface DailySales {
  day: string;
  /** Null for days that haven't happened yet. */
  thisWeek: number | null;
  lastWeek: number;
}

export interface StockItem {
  id: string;
  name: string;
  category: string | null;
  onHand: number;
  status: StockStatus;
}

const pesos = (amount: string) => toCents(amount) / 100;

/** "Sunday": the store's current weekday, for "vs last Sunday". */
export function storeWeekday(overview: Pick<Overview, "as_of" | "timezone">): string {
  return new Intl.DateTimeFormat("en-PH", { weekday: "long", timeZone: overview.timezone }).format(
    new Date(overview.as_of),
  );
}

/** Percent change against the same weekday last week. No baseline, no percentage. */
export function compareCounts(current: number, previous: number, weekday: string): Pick<Kpi, "change" | "trend"> {
  if (previous === 0) return { change: `No sales last ${weekday}`, trend: "neutral" };
  const percent = Math.round(((current - previous) / previous) * 100);
  if (percent === 0) return { change: `Same as last ${weekday}`, trend: "neutral" };
  return { change: `${Math.abs(percent)}% vs last ${weekday}`, trend: percent > 0 ? "up" : "down" };
}

function compareMargins(current: string | null, previous: string | null, weekday: string): Pick<Kpi, "change" | "trend"> {
  if (current === null) return { change: "No sales yet today", trend: "neutral" };
  if (previous === null) return { change: `No sales last ${weekday}`, trend: "neutral" };
  const points = Math.round((Number(current) - Number(previous)) * 1000) / 10;
  if (points === 0) return { change: `Same as last ${weekday}`, trend: "neutral" };
  return { change: `${Math.abs(points).toFixed(1)} pts vs last ${weekday}`, trend: points > 0 ? "up" : "down" };
}

/**
 * Four KPIs either way, so the strip keeps its 2×2 / 4-column layout.
 * Owners and managers: sales, transactions, gross margin, items running low.
 * Cashiers: their own sales and transactions, then running low and out of stock (no costs).
 */
export function buildKpis(overview: Overview): Kpi[] {
  const weekday = storeWeekday(overview);
  const { today, same_day_last_week: lastWeek } = overview;
  const mine = overview.sales_scope === "mine";

  const kpis: Kpi[] = [
    {
      id: "sales",
      label: mine ? "Your sales today" : "Sales today",
      value: formatPesoWhole(pesos(today.sales)),
      ...compareCounts(toCents(today.sales), toCents(lastWeek.sales), weekday),
    },
    {
      id: "transactions",
      label: mine ? "Your transactions" : "Transactions",
      value: formatNumber(today.transactions),
      ...compareCounts(today.transactions, lastWeek.transactions, weekday),
    },
  ];

  if (overview.costs_visible) {
    kpis.push(
      {
        id: "margin",
        label: "Gross margin today",
        value: today.gross_margin === null ? "—" : formatPercent(Number(today.gross_margin)),
        ...compareMargins(today.gross_margin, lastWeek.gross_margin, weekday),
      },
      {
        id: "low-stock",
        label: "Items running low",
        value: formatNumber(overview.low_stock_count + overview.out_of_stock_count),
        change: `${formatNumber(overview.out_of_stock_count)} out of stock`,
        trend: "neutral",
      },
    );
  } else {
    kpis.push(
      {
        id: "low-stock",
        label: "Running low",
        value: formatNumber(overview.low_stock_count),
        change: "At or below reorder level",
        trend: "neutral",
      },
      {
        id: "out-of-stock",
        label: "Out of stock",
        value: formatNumber(overview.out_of_stock_count),
        change: "Can't be sold until restocked",
        trend: "neutral",
      },
    );
  }
  return kpis;
}

/** "2026-11-22" → "Sun". The date is already the store's calendar day, so format it as UTC. */
function shortWeekday(isoDate: string): string {
  return new Intl.DateTimeFormat("en-PH", { weekday: "short", timeZone: "UTC" }).format(new Date(`${isoDate}T00:00:00Z`));
}

export function buildWeeklySales(overview: Overview): DailySales[] {
  return overview.week.map((day) => ({
    day: shortWeekday(day.date),
    thisWeek: day.sales === null ? null : pesos(day.sales),
    lastWeek: pesos(day.last_week_sales),
  }));
}

/** Plain-language chart summary for screen readers: this week so far vs the same days last week. */
export function weeklySummary(overview: Overview): string {
  const elapsed = overview.week.filter((day) => day.sales !== null);
  const thisWeek = elapsed.reduce((sum, day) => sum + toCents(day.sales ?? "0"), 0);
  const lastWeek = elapsed.reduce((sum, day) => sum + toCents(day.last_week_sales), 0);
  const days = elapsed.length === 1 ? "1 day" : `${elapsed.length} days`;
  const whose = overview.sales_scope === "mine" ? "Your sales" : "Sales";
  return `${whose} this week so far (${days}): ${formatPesoWhole(thisWeek / 100)}. Same days last week: ${formatPesoWhole(lastWeek / 100)}.`;
}

export function buildStockItems(items: StockWatchItem[]): StockItem[] {
  return items.map((item) => ({
    id: item.id,
    name: item.name,
    category: item.category,
    onHand: item.stock_on_hand,
    status: item.stock_status,
  }));
}

/**
 * Y-axis ticks: five evenly spaced round numbers (0 and four steps) that cover `max`.
 * Steps are 1, 2, 2.5 or 5 times a power of ten, so labels stay readable.
 */
export function niceTicks(max: number): number[] {
  const rough = Math.max(max, 1) / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= rough) ?? 10 * magnitude;
  const safeStep = Math.max(step, 50); // an empty week still shows ₱0–₱200, not ₱0–₱1
  return [0, 1, 2, 3, 4].map((i) => i * safeStep);
}

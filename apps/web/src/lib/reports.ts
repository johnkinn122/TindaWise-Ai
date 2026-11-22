/**
 * Reports page logic without fetching: reading the URL, wording, labels and CSV layouts.
 * Figures are defined in services/api/app/services/reports.py; nothing is recomputed here except
 * display formatting. Sales are net of refunds and can be negative, so amounts are read signed.
 */

import type { ReportParams } from "@/lib/api/reports";
import type { ReportPeriod, ReportPreset, ReportProductSort, SalesReport } from "@/lib/api/types";
import { percentChange, pointChange } from "@/lib/compare";
import { toCsv } from "@/lib/csv";
import { formatNumber, formatPercent, formatPeso, formatPesoWhole } from "@/lib/format";
import { signedCents, toCents } from "@/lib/money";
import type { Kpi } from "@/lib/overview";

export const reportPresets: { id: ReportPreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "yesterday", label: "Yesterday" },
  { id: "last_7_days", label: "Last 7 days" },
  { id: "last_30_days", label: "Last 30 days" },
  { id: "this_month", label: "This month" },
  { id: "last_month", label: "Last month" },
];

const SORTS: ReportProductSort[] = ["sales", "gross_profit", "quantity"];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

type RawParams = Record<string, string | string[] | undefined>;
const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

/** Only well-formed values reach the API; anything else falls back to its default. */
export function parseReportParams(raw: RawParams): ReportParams {
  const presetParam = first(raw.preset);
  const preset = reportPresets.find((p) => p.id === presetParam)?.id;
  const start = first(raw.start);
  const end = first(raw.end);
  const sortParam = first(raw.sort);
  const custom = start && end && ISO_DATE.test(start) && ISO_DATE.test(end);
  return {
    ...(custom ? { start, end } : { preset: preset ?? "last_7_days" }),
    sort: SORTS.includes(sortParam as ReportProductSort) ? (sortParam as ReportProductSort) : "sales",
  };
}

/** Query string for a report link; `changes` replaces keys (undefined removes them). */
export function reportQuery(params: ReportParams, changes: Partial<Record<keyof ReportParams, string | undefined>> = {}) {
  const merged: Record<string, string | undefined> = {
    preset: params.preset,
    start: params.start,
    end: params.end,
    sort: params.sort === "sales" ? undefined : params.sort,
    ...changes,
  };
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(merged)) if (value) query.set(key, value);
  return query.toString();
}

const day = (iso: string) => new Date(`${iso}T00:00:00Z`);
const rangeFormatter = new Intl.DateTimeFormat("en-PH", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

/** "Nov 16 – 22, 2026" or "Nov 22, 2026". Dates are store days, so they're formatted as UTC. */
export function formatPeriod(period: ReportPeriod): string {
  return period.start === period.end
    ? rangeFormatter.format(day(period.start))
    : rangeFormatter.formatRange(day(period.start), day(period.end));
}

function comparisonWording(days: number) {
  return days === 1
    ? { against: "the day before", noBaseline: "No sales the day before" }
    : { against: `the previous ${days} days`, noBaseline: `No sales in the previous ${days} days` };
}

/** Net sales, gross profit, gross margin and transactions, each against the previous period. */
export function buildReportKpis(report: SalesReport): Kpi[] {
  const { summary: now, previous_summary: before } = report;
  const wording = comparisonWording(report.period.days);
  return [
    {
      id: "sales",
      label: "Net sales",
      value: formatPesoWhole(signedCents(now.sales) / 100),
      ...percentChange(signedCents(now.sales), signedCents(before.sales), wording),
    },
    {
      id: "profit",
      label: "Gross profit",
      value: formatPesoWhole(signedCents(now.gross_profit) / 100),
      ...percentChange(signedCents(now.gross_profit), signedCents(before.gross_profit), wording),
    },
    {
      id: "margin",
      label: "Gross margin",
      value: now.gross_margin === null ? "—" : formatPercent(Number(now.gross_margin)),
      ...pointChange(now.gross_margin, before.gross_margin, { ...wording, noCurrent: "No sales in this period" }),
    },
    {
      id: "transactions",
      label: "Transactions",
      value: formatNumber(now.transactions),
      ...percentChange(now.transactions, before.transactions, wording),
    },
  ];
}

const shortDay = new Intl.DateTimeFormat("en-PH", { month: "short", day: "numeric", timeZone: "UTC" });
const longDay = new Intl.DateTimeFormat("en-PH", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
const shortMonth = new Intl.DateTimeFormat("en-PH", { month: "short", timeZone: "UTC" });
const longMonth = new Intl.DateTimeFormat("en-PH", { month: "long", year: "numeric", timeZone: "UTC" });

export const granularityLabels: Record<SalesReport["granularity"], string> = {
  day: "by day",
  week: "by week",
  month: "by month",
};

/** Axis label and tooltip/table label for one bucket. */
export function bucketLabels(start: string, granularity: SalesReport["granularity"]) {
  if (granularity === "month") return { short: shortMonth.format(day(start)), long: longMonth.format(day(start)) };
  if (granularity === "week") return { short: shortDay.format(day(start)), long: `Week of ${shortDay.format(day(start))}` };
  return { short: shortDay.format(day(start)), long: longDay.format(day(start)) };
}

/**
 * "Gross ₱1,200.00 − refunds ₱150.00 (2) = net ₱1,050.00", or null when the period had no refunds.
 * Shown under the KPIs so the net figure is never a surprise.
 */
export function refundBreakdown(report: SalesReport): string | null {
  const { summary } = report;
  if (summary.refund_count === 0) return null;
  const count = summary.refund_count === 1 ? "1 refund" : `${formatNumber(summary.refund_count)} refunds`;
  return `Gross sales ${formatPeso(toCents(summary.gross_sales) / 100)} − ${count} ${formatPeso(toCents(summary.refunds) / 100)} = net sales ${formatPeso(signedCents(summary.sales) / 100)}`;
}

export interface SeriesRow {
  label: string;
  longLabel: string;
  /** Net sales (can be negative). */
  sales: number;
  refunds: number;
  transactions: number;
  grossProfit: number;
}

export function buildSeries(report: SalesReport): SeriesRow[] {
  return report.series.map((point) => {
    const labels = bucketLabels(point.start, report.granularity);
    return {
      label: labels.short,
      longLabel: labels.long,
      sales: signedCents(point.sales) / 100,
      refunds: toCents(point.refunds) / 100,
      transactions: point.transactions,
      grossProfit: signedCents(point.gross_profit) / 100,
    };
  });
}

/** Text summary of the sales chart for screen readers: total, and the best bucket. */
export function seriesSummary(report: SalesReport): string {
  const total = formatPesoWhole(signedCents(report.summary.sales) / 100);
  const rows = buildSeries(report);
  const best = rows.reduce<SeriesRow | null>((top, row) => (row.sales > (top?.sales ?? 0) ? row : top), null);
  const by = granularityLabels[report.granularity];
  return best
    ? `Net sales ${by}, ${formatPeriod(report.period)}: ${total} in total. Highest: ${best.longLabel}, ${formatPesoWhole(best.sales)}.`
    : report.summary.refund_count > 0
      ? `Net sales ${by}, ${formatPeriod(report.period)}: ${total}, refunds only.`
      : `Net sales ${by}, ${formatPeriod(report.period)}: no sales.`;
}

export const paymentLabels: Record<SalesReport["payments"][number]["method"], string> = {
  cash: "Cash",
  e_wallet: "E-wallet",
};

export const productSortLabels: Record<ReportProductSort, string> = {
  sales: "Sales",
  gross_profit: "Gross profit",
  quantity: "Quantity",
};

// ── CSV ─────────────────────────────────────────────────────────────────────

export const exportKinds = ["sales", "products", "categories", "suppliers"] as const;
export type ExportKind = (typeof exportKinds)[number];

export function reportCsv(report: SalesReport, kind: ExportKind): { filename: string; body: string } {
  const range = `${report.period.start}-to-${report.period.end}`;
  const ratio = (value: string | null) => (value === null ? "" : (Number(value) * 100).toFixed(1));
  switch (kind) {
    case "sales":
      return {
        filename: `tindawise-sales-${report.granularity}-${range}.csv`,
        body: toCsv(
          [
            `${report.granularity === "day" ? "Date" : `${report.granularity} starting`}`,
            "Net sales (PHP)",
            "Refunds (PHP)",
            "Transactions",
            "Gross profit (PHP)",
          ],
          report.series.map((p) => [p.start, p.sales, p.refunds, p.transactions, p.gross_profit]),
        ),
      };
    case "products":
      return {
        filename: `tindawise-products-${range}.csv`,
        body: toCsv(
          ["Product", "SKU", "Unit", "Net quantity", "Net sales (PHP)", "Gross profit (PHP)", "Gross margin (%)"],
          report.products.map((p) => [p.name, p.sku, p.unit, p.quantity, p.sales, p.gross_profit, ratio(p.gross_margin)]),
        ),
      };
    case "categories":
      return {
        filename: `tindawise-categories-${range}.csv`,
        body: toCsv(
          ["Category", "Net quantity", "Net sales (PHP)", "Gross profit (PHP)"],
          report.categories.map((c) => [c.name, c.quantity, c.sales, c.gross_profit]),
        ),
      };
    case "suppliers":
      return {
        filename: `tindawise-purchases-${range}.csv`,
        body: toCsv(
          ["Supplier", "Deliveries", "Received value (PHP)"],
          report.suppliers.map((s) => [s.name, s.deliveries, s.received_value]),
        ),
      };
  }
}

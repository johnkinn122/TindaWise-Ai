import { describe, expect, it } from "vitest";
import type { SalesReport } from "@/lib/api/types";
import { percentChange } from "@/lib/compare";
import { csvCell, toCsv } from "@/lib/csv";
import { signedCents } from "@/lib/money";
import {
  buildReportKpis,
  buildSeries,
  bucketLabels,
  formatPeriod,
  parseReportParams,
  refundBreakdown,
  reportCsv,
  reportQuery,
  seriesSummary,
} from "@/lib/reports";

const summary = (sales: string, profit: string, transactions: number, margin: string | null, refunds = "0.00", refundCount = 0) => ({
  gross_sales: (signedCents(sales) / 100 + Number(refunds)).toFixed(2),
  refunds,
  refund_count: refundCount,
  sales,
  transactions,
  average_sale: null,
  gross_profit: profit,
  gross_margin: margin,
  items_sold: 0,
});

function report(overrides: Partial<SalesReport> = {}): SalesReport {
  return {
    timezone: "Asia/Manila",
    currency: "PHP",
    period: { start: "2026-11-16", end: "2026-11-22", days: 7 },
    previous_period: { start: "2026-11-09", end: "2026-11-15", days: 7 },
    granularity: "day",
    summary: summary("1150.00", "250.00", 23, "0.2174"),
    previous_summary: summary("1000.00", "200.00", 25, "0.2000"),
    series: [
      { start: "2026-11-21", sales: "150.00", refunds: "0.00", transactions: 3, gross_profit: "30.00" },
      { start: "2026-11-22", sales: "1000.00", refunds: "0.00", transactions: 20, gross_profit: "220.00" },
    ],
    products: [
      { product_id: "p", name: "=HYPERLINK(\"x\")", sku: "S-1", unit: "pcs", quantity: 3, sales: "30.00", gross_profit: "-5.00", gross_margin: "-0.1667" },
    ],
    product_count: 1,
    product_sort: "sales",
    categories: [],
    payments: [],
    suppliers: [],
    purchases_total: "0.00",
    ...overrides,
  };
}

describe("parseReportParams", () => {
  it("accepts known presets and well-formed custom ranges only", () => {
    expect(parseReportParams({})).toEqual({ preset: "last_7_days", sort: "sales" });
    expect(parseReportParams({ preset: "this_month", sort: "quantity" })).toEqual({ preset: "this_month", sort: "quantity" });
    expect(parseReportParams({ start: "2026-01-01", end: "2026-01-31", preset: "today" })).toEqual({
      start: "2026-01-01",
      end: "2026-01-31",
      sort: "sales",
    });
    expect(parseReportParams({ preset: "forever", start: "yesterday", end: "x", sort: "cost" })).toEqual({
      preset: "last_7_days",
      sort: "sales",
    });
  });

  it("builds links that keep the period and drop the default sort", () => {
    expect(reportQuery({ preset: "today", sort: "sales" })).toBe("preset=today");
    expect(reportQuery({ preset: "today", sort: "sales" }, { sort: "gross_profit" })).toBe("preset=today&sort=gross_profit");
  });
});

describe("labels", () => {
  it("formats periods and buckets as store days", () => {
    expect(formatPeriod({ start: "2026-11-16", end: "2026-11-22", days: 7 })).toMatch(/^Nov 16\s*–\s*22, 2026$/);
    expect(formatPeriod({ start: "2026-11-22", end: "2026-11-22", days: 1 })).toBe("Nov 22, 2026");
    expect(bucketLabels("2026-11-15", "week")).toEqual({ short: "Nov 15", long: "Week of Nov 15" });
    expect(bucketLabels("2026-11-01", "month")).toEqual({ short: "Nov", long: "November 2026" });
  });

  it("summarizes the chart for screen readers", () => {
    expect(seriesSummary(report())).toMatch(/₱1,150 in total\. Highest: Sun, Nov 22, ₱1,000\.$/);
  });
});

describe("buildReportKpis", () => {
  it("compares every figure with the previous period", () => {
    expect(buildReportKpis(report()).map((k) => [k.label, k.value, k.change])).toEqual([
      ["Net sales", "₱1,150", "15% vs the previous 7 days"],
      ["Gross profit", "₱250", "25% vs the previous 7 days"],
      ["Gross margin", "21.7%", "1.7 pts vs the previous 7 days"],
      ["Transactions", "23", "8% vs the previous 7 days"],
    ]);
  });

  it("handles a loss and a one-day period", () => {
    const kpis = buildReportKpis(
      report({
        period: { start: "2026-11-22", end: "2026-11-22", days: 1 },
        summary: summary("100.00", "-20.00", 1, "-0.2000"),
        previous_summary: summary("0.00", "0.00", 0, null),
      }),
    );
    expect(kpis[1]).toMatchObject({ value: "-₱20", change: "No sales the day before" });
  });
});

describe("money and comparisons", () => {
  it("reads negative amounts exactly", () => {
    expect(signedCents("-5.10")).toBe(-510);
    expect(signedCents("12.00")).toBe(1200);
  });

  it("measures change against the size of a negative baseline", () => {
    expect(percentChange(-500, -1000, { against: "x", noBaseline: "n" })).toEqual({ change: "50% vs x", trend: "up" });
  });
});

describe("CSV", () => {
  it("neutralizes formulas in text but leaves numbers alone", () => {
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(csvCell("@cmd")).toBe("'@cmd");
    expect(csvCell("-5.00")).toBe("-5.00");
    expect(csvCell(-5)).toBe("-5");
    expect(csvCell('Say "hi", please')).toBe('"Say ""hi"", please"');
    expect(csvCell(null)).toBe("");
  });

  it("writes a BOM, a header and CRLF lines", () => {
    expect(toCsv(["A", "B"], [[1, "x"]])).toBe("\uFEFFA,B\r\n1,x\r\n");
  });

  it("exports products with a guarded name and a dated filename", () => {
    const { filename, body } = reportCsv(report(), "products");
    expect(filename).toBe("tindawise-products-2026-11-16-to-2026-11-22.csv");
    expect(body.split("\r\n")[1]).toBe(`"'=HYPERLINK(""x"")",S-1,pcs,3,30.00,-5.00,-16.7`);
  });
});

describe("refunds", () => {
  const withRefunds = report({
    summary: summary("1050.00", "200.00", 23, "0.1905", "150.00", 2),
    series: [
      { start: "2026-11-21", sales: "-40.00", refunds: "190.00", transactions: 3, gross_profit: "-40.00" },
      { start: "2026-11-22", sales: "1090.00", refunds: "0.00", transactions: 20, gross_profit: "240.00" },
    ],
  });

  it("spells out gross minus refunds, only when there were refunds", () => {
    expect(refundBreakdown(withRefunds)).toBe("Gross sales ₱1,200.00 − 2 refunds ₱150.00 = net sales ₱1,050.00");
    expect(refundBreakdown(report())).toBeNull();
  });

  it("keeps negative days negative in the chart and the CSV", () => {
    expect(buildSeries(withRefunds)[0]).toMatchObject({ sales: -40, refunds: 190, grossProfit: -40 });
    const lines = reportCsv(withRefunds, "sales").body.split(String.fromCharCode(13, 10)); // CRLF
    expect(lines[0].replace(String.fromCharCode(0xfeff), "")).toBe("Date,Net sales (PHP),Refunds (PHP),Transactions,Gross profit (PHP)");
    expect(lines[1]).toBe("2026-11-21,-40.00,190.00,3,-40.00");
  });

  it("describes a period with only refunds", () => {
    const refundsOnly = report({
      summary: summary("-30.00", "-10.00", 0, null, "30.00", 1),
      series: [{ start: "2026-11-22", sales: "-30.00", refunds: "30.00", transactions: 0, gross_profit: "-10.00" }],
    });
    expect(seriesSummary(refundsOnly)).toMatch(/: -₱30, refunds only\.$/);
    expect(buildReportKpis(refundsOnly)[0]).toMatchObject({ label: "Net sales", value: "-₱30" });
  });
});

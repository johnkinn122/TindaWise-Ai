import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReorderCard } from "@/components/dashboard/reorder-card";
import type { Overview } from "@/lib/api/types";
import { buildKpis, buildWeeklySales, compareCounts, niceTicks, storeWeekday, weeklySummary } from "@/lib/overview";

const week = ["15", "16", "17", "18", "19", "20", "21"].map((d, i) => ({
  date: `2026-11-${d}`,
  sales: i <= 3 ? "100.00" : null, // Sunday to Wednesday have happened
  last_week_sales: "80.00",
}));

function overview(overrides: Partial<Overview> = {}): Overview {
  return {
    // 10:00 Wednesday in Manila; still Tuesday in UTC (02:00), which must not matter.
    as_of: "2026-11-18T02:00:00Z",
    timezone: "Asia/Manila",
    currency: "PHP",
    sales_scope: "store",
    costs_visible: true,
    today: { sales: "1150.00", transactions: 23, gross_margin: "0.2240" },
    same_day_last_week: { sales: "1000.00", transactions: 25, gross_margin: "0.2130" },
    week,
    low_stock_count: 4,
    out_of_stock_count: 2,
    stock_to_watch: [],
    reorder: { lines: [], total_count: 0, lookback_days: 14, estimated_cost: null },
    ...overrides,
  };
}

describe("storeWeekday", () => {
  it("uses the store's time zone, not the server's", () => {
    expect(storeWeekday(overview())).toBe("Wednesday");
  });
});

describe("compareCounts", () => {
  it("rounds the change and names the weekday", () => {
    expect(compareCounts(115, 100, "Friday")).toEqual({ change: "15% vs last Friday", trend: "up" });
    expect(compareCounts(92, 100, "Friday")).toEqual({ change: "8% vs last Friday", trend: "down" });
    expect(compareCounts(100, 100, "Friday")).toEqual({ change: "Same as last Friday", trend: "neutral" });
  });

  it("never invents a percentage without a baseline", () => {
    expect(compareCounts(500, 0, "Friday")).toEqual({ change: "No sales last Friday", trend: "neutral" });
  });
});

describe("buildKpis", () => {
  it("gives owners sales, transactions, margin and low stock", () => {
    const kpis = buildKpis(overview());
    expect(kpis.map((k) => [k.label, k.value, k.change])).toEqual([
      ["Sales today", "₱1,150", "15% vs last Wednesday"],
      ["Transactions", "23", "8% vs last Wednesday"],
      ["Gross margin today", "22.4%", "1.1 pts vs last Wednesday"],
      ["Items running low", "6", "2 out of stock"],
    ]);
  });

  it("shows a dash, not 0%, when there are no sales yet", () => {
    const margin = buildKpis(overview({ today: { sales: "0.00", transactions: 0, gross_margin: null } }))[2];
    expect(margin).toMatchObject({ value: "—", change: "No sales yet today", trend: "neutral" });
  });

  it("gives cashiers their own figures and no margin", () => {
    const kpis = buildKpis(
      overview({
        sales_scope: "mine",
        costs_visible: false,
        today: { sales: "300.00", transactions: 4, gross_margin: null },
        same_day_last_week: { sales: "0.00", transactions: 0, gross_margin: null },
      }),
    );
    expect(kpis.map((k) => k.label)).toEqual(["Your sales today", "Your transactions", "Running low", "Out of stock"]);
    expect(kpis.map((k) => k.value)).toEqual(["₱300", "4", "4", "2"]);
    expect(kpis.some((k) => /margin/i.test(k.label))).toBe(false);
  });
});

describe("weekly sales", () => {
  it("labels days and keeps days that haven't happened empty", () => {
    const data = buildWeeklySales(overview());
    expect(data.map((d) => d.day)).toEqual(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]);
    expect(data[3]).toEqual({ day: "Wed", thisWeek: 100, lastWeek: 80 });
    expect(data[4]!.thisWeek).toBeNull();
  });

  it("summarizes only the days so far", () => {
    expect(weeklySummary(overview())).toBe("Sales this week so far (4 days): ₱400. Same days last week: ₱320.");
  });
});

describe("niceTicks", () => {
  it.each([
    [0, [0, 50, 100, 150, 200]],
    [189, [0, 50, 100, 150, 200]],
    [18420, [0, 5000, 10000, 15000, 20000]],
    [21000, [0, 10000, 20000, 30000, 40000]],
    [900, [0, 250, 500, 750, 1000]],
  ])("covers %d with round steps", (max, ticks) => {
    expect(niceTicks(max)).toEqual(ticks);
    expect(ticks.at(-1)).toBeGreaterThanOrEqual(max);
  });
});

describe("ReorderCard", () => {
  const reorder: Overview["reorder"] = {
    lines: [
      {
        product_id: "a",
        name: "Coca-Cola 1.5L",
        unit: "btl",
        stock_on_hand: 0,
        reorder_level: 12,
        sold_recently: 30,
        suggested_quantity: 30,
        unit_cost: "68.00",
      },
    ],
    total_count: 3,
    lookback_days: 14,
    estimated_cost: "2040.00",
  };

  it("lists quantities and cost, and says it's a rule, not a forecast", () => {
    render(<ReorderCard reorder={reorder} canOrder />);
    expect(screen.getByRole("heading", { name: "Reorder suggestions" })).toBeInTheDocument();
    expect(screen.getByText("30 btl")).toBeInTheDocument();
    expect(screen.getByText("₱2,040.00")).toBeInTheDocument();
    expect(screen.getByText(/A simple rule, not a forecast/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See products by stock" })).toHaveAttribute("href", "/products?sort=stock");
    expect(screen.getByRole("button", { name: "Create purchase order" })).toBeEnabled();
  });

  it("hides cost and ordering from cashiers", () => {
    render(<ReorderCard reorder={{ ...reorder, estimated_cost: null }} canOrder={false} />);
    expect(screen.queryByText("Estimated cost")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create purchase order" })).not.toBeInTheDocument();
  });

  it("says plainly when nothing needs reordering", () => {
    render(<ReorderCard reorder={{ ...reorder, lines: [], total_count: 0, estimated_cost: "0.00" }} canOrder />);
    expect(screen.getByText(/Nothing to reorder/)).toBeInTheDocument();
  });
});

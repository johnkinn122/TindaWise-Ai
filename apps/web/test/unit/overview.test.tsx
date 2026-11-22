import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReorderCard } from "@/components/dashboard/reorder-card";
import type { Overview, ReorderLine } from "@/lib/api/types";
import { niceTicks } from "@/lib/chart";
import {
  buildKpis,
  buildWeeklySales,
  compareCounts,
  reorderReason,
  storeWeekday,
  weeklySummary,
} from "@/lib/overview";

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
    today: { sales: "1150.00", refunds: "0.00", transactions: 23, gross_margin: "0.2240" },
    same_day_last_week: { sales: "1000.00", refunds: "0.00", transactions: 25, gross_margin: "0.2130" },
    week,
    low_stock_count: 4,
    out_of_stock_count: 2,
    stock_to_watch: [],
    reorder: { lines: [], total_count: 0, window_days: 28, cover_days: 10, estimated_cost: null },
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
    const margin = buildKpis(overview({ today: { sales: "0.00", refunds: "0.00", transactions: 0, gross_margin: null } }))[2];
    expect(margin).toMatchObject({ value: "—", change: "No sales yet today", trend: "neutral" });
  });

  it("gives cashiers their own figures and no margin", () => {
    const kpis = buildKpis(
      overview({
        sales_scope: "mine",
        costs_visible: false,
        today: { sales: "300.00", refunds: "0.00", transactions: 4, gross_margin: null },
        same_day_last_week: { sales: "0.00", refunds: "0.00", transactions: 0, gross_margin: null },
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
  it("goes below zero only when a value does (a day with more refunds than sales)", () => {
    expect(niceTicks(1000, -300)).toEqual([-500, 0, 500, 1000]);
    expect(niceTicks(0, -80)).toEqual([-100, -50, 0]);
    expect(niceTicks(900, 0)).toEqual([0, 250, 500, 750, 1000]);
  });
});

describe("refunds on the Overview", () => {
  it("reads negative net sales and says how much was refunded", () => {
    const [sales] = buildKpis(
      overview({
        today: { sales: "-50.00", refunds: "250.00", transactions: 2, gross_margin: null },
        same_day_last_week: { sales: "100.00", refunds: "0.00", transactions: 1, gross_margin: "0.2000" },
      }),
    );
    expect(sales).toMatchObject({ value: "-₱50", change: "150% vs last Wednesday · ₱250 refunded", trend: "down" });
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
        on_order: 0,
        reorder_level: 12,
        suggested_quantity: 30,
        basis: "recent_sales",
        daily_rate: "2.5",
        in_stock_days: 21,
        lead_time_days: 2,
        lead_time_source: "supplier",
        supplier_name: "Coca-Cola Depot",
        unit_cost: "68.00",
      },
    ],
    total_count: 3,
    window_days: 28,
    cover_days: 10,
    estimated_cost: "2040.00",
  };

  it("lists quantities, cost and the reason for each line", () => {
    render(<ReorderCard reorder={reorder} canOrder />);
    expect(screen.getByRole("heading", { name: "Reorder suggestions" })).toBeInTheDocument();
    expect(screen.getByText("30 btl")).toBeInTheDocument();
    expect(screen.getByText("₱2,040.00")).toBeInTheDocument();
    expect(
      screen.getByText("0 on hand · about 2.5 sold a day · 2-day delivery from Coca-Cola Depot"),
    ).toBeInTheDocument();
    expect(screen.getByText(/covers the delivery time plus 10 days/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set delivery times on suppliers" })).toHaveAttribute("href", "/suppliers");
    expect(screen.getByRole("link", { name: "See products by stock" })).toHaveAttribute("href", "/products?sort=stock");
    expect(screen.getByRole("button", { name: "Create purchase order" })).toBeEnabled();
  });

  it("hides cost and ordering from cashiers", () => {
    render(<ReorderCard reorder={{ ...reorder, estimated_cost: null }} canOrder={false} />);
    expect(screen.queryByText("Estimated cost")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create purchase order" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Set delivery times on suppliers" })).not.toBeInTheDocument();
  });

  it("says plainly when nothing needs reordering", () => {
    render(<ReorderCard reorder={{ ...reorder, lines: [], total_count: 0, estimated_cost: "0.00" }} canOrder />);
    expect(screen.getByText(/Nothing to reorder/)).toBeInTheDocument();
  });
});

describe("reorderReason", () => {
  const base: ReorderLine = {
    product_id: "a",
    name: "Item",
    unit: "pcs",
    stock_on_hand: 3,
    on_order: 0,
    reorder_level: 5,
    suggested_quantity: 7,
    basis: "recent_sales",
    daily_rate: "1.0",
    in_stock_days: 28,
    lead_time_days: 3,
    lead_time_source: "store_default",
    supplier_name: null,
    unit_cost: null,
  };

  it("explains a suggestion from recent sales with the store's default delivery time", () => {
    expect(reorderReason(base)).toBe("3 on hand · about 1 sold a day · 3-day delivery (store default)");
  });

  it("names the supplier and units already on order", () => {
    expect(
      reorderReason({ ...base, on_order: 1200, lead_time_days: 1, lead_time_source: "supplier", supplier_name: "Puregold" }),
    ).toBe("3 on hand · 1,200 on order · about 1 sold a day · 1-day delivery from Puregold");
  });

  it("says when the reorder level was used instead of sales", () => {
    expect(reorderReason({ ...base, basis: "reorder_level", daily_rate: null })).toBe(
      "3 on hand · little sales history yet, so up to twice the reorder level",
    );
  });

  it("pluralises the delivery time", () => {
    expect(reorderReason({ ...base, lead_time_days: 0 })).toContain("0-day delivery");
    expect(reorderReason({ ...base, lead_time_days: 14 })).toContain("14-day delivery");
  });
});

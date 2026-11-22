import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { ResiboCard } from "@/components/dashboard/resibo-card";
import { StockBadge } from "@/components/dashboard/stock-badge";
import { MovementHistory } from "@/components/products/movement-history";
import { sampleReorderSuggestion } from "@/lib/sample-data";

describe("StockBadge", () => {
  it.each([
    ["in_stock", "In stock"],
    ["low_stock", "Low stock"],
    ["out_of_stock", "Out of stock"],
  ] as const)("shows %s as text, not color alone", (status, label) => {
    render(<StockBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe("KpiStrip", () => {
  it("announces the trend direction to screen readers", () => {
    render(
      <KpiStrip
        kpis={[
          { id: "a", label: "Sales today", value: "₱100", change: "5% vs last Friday", trend: "up" },
          { id: "b", label: "Margin", value: "20%", change: "1 pt", trend: "down" },
        ]}
      />,
    );
    expect(screen.getByText("Sales today")).toBeInTheDocument();
    expect(screen.getByText("Up", { exact: false })).toHaveClass("sr-only");
    expect(screen.getByText("Down", { exact: false })).toHaveClass("sr-only");
  });
});

describe("ResiboCard", () => {
  it("totals the suggested lines exactly", () => {
    render(<ResiboCard suggestion={sampleReorderSuggestion} />);
    // 48 × 14.50 + 24 × 68.00 + 36 × 15.25 = 696 + 1632 + 549 = 2877
    expect(screen.getByText((text) => text.replace(/\s/g, "") === "₱2,877.00")).toBeInTheDocument();
  });

  it("keeps actions disabled until purchase orders exist", () => {
    render(<ResiboCard suggestion={sampleReorderSuggestion} />);
    expect(screen.getByRole("button", { name: "Create purchase order" })).toBeDisabled();
  });
});

describe("MovementHistory", () => {
  it("shows an empty message when there are no changes", () => {
    render(<MovementHistory movements={[]} timeZone="Asia/Manila" />);
    expect(screen.getByText("No stock changes yet.")).toBeInTheDocument();
  });

  it("shows signed changes and balances", () => {
    render(
      <MovementHistory
        timeZone="Asia/Manila"
        movements={[
          {
            id: "2",
            product_id: "p",
            quantity_change: -3,
            balance_after: 7,
            reason: "damage",
            note: "Dented cans",
            created_at: "2026-11-22T02:00:00Z",
          },
          {
            id: "1",
            product_id: "p",
            quantity_change: 10,
            balance_after: 10,
            reason: "initial",
            note: null,
            created_at: "2026-11-22T01:00:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("Damaged or expired")).toBeInTheDocument();
    expect(screen.getByText("Dented cans")).toBeInTheDocument();
    expect(screen.getByText("−3")).toBeInTheDocument();
    expect(screen.getByText("+10")).toBeInTheDocument();
  });
});

import { describe, expect, it } from "vitest";
import type { InventorySummary } from "@/lib/api/types";
import {
  buildInventoryKpis,
  formatChange,
  hasFilters,
  inventoryFilters,
  inventoryHref,
  parseInventoryParams,
  sourceHref,
  sourceLabel,
} from "@/lib/inventory";

const ID = "5cae6945-e388-40fa-b7b3-5a2b10d65307";

describe("parseInventoryParams", () => {
  it("keeps well-formed filters", () => {
    expect(
      parseInventoryParams({ q: "  sardines ", reason: "sale", who: ID, product: ID, start: "2026-11-01", end: "2026-11-22", page: "3" }),
    ).toEqual({ q: "sardines", reason: "sale", who: ID, product: ID, start: "2026-11-01", end: "2026-11-22", page: 3 });
  });

  it("drops anything malformed, as if it weren't there", () => {
    expect(
      parseInventoryParams({ q: "   ", reason: "stolen", who: "1 OR 1=1", product: "abc", start: "22/11/2026", end: "", page: "-2" }),
    ).toEqual({ page: 1 });
    expect(parseInventoryParams({ page: "two" })).toEqual({ page: 1 });
  });

  it("takes the first of repeated parameters and caps the search length", () => {
    expect(parseInventoryParams({ reason: ["damage", "sale"], q: "x".repeat(150) })).toEqual({
      reason: "damage",
      q: "x".repeat(100),
      page: 1,
    });
  });
});

describe("filters and links", () => {
  const params = parseInventoryParams({ q: "soap", reason: "damage", page: "2" });

  it("lists filters without the page", () => {
    expect(inventoryFilters(params)).toEqual({ q: "soap", reason: "damage" });
    expect(hasFilters(params)).toBe(true);
    expect(hasFilters({ page: 4 })).toBe(false);
  });

  it("builds links that keep the view and drop removed filters", () => {
    expect(inventoryHref(params)).toBe("/inventory?q=soap&reason=damage");
    expect(inventoryHref(params, { reason: undefined })).toBe("/inventory?q=soap");
    expect(inventoryHref(params, { page: "3" })).toBe("/inventory?q=soap&reason=damage&page=3");
    expect(inventoryHref({ page: 1 })).toBe("/inventory");
  });

  it("opens the receipt for sales and refunds, the order for deliveries", () => {
    expect(sourceHref({ kind: "sale", id: "s1", code: "S-000052" })).toBe("/sales/s1");
    expect(sourceHref({ kind: "refund", id: "s1", code: "R-000007" })).toBe("/sales/s1");
    expect(sourceHref({ kind: "purchase_order", id: "po1", code: "PO-000014" })).toBe("/purchase-orders/po1");
    expect(sourceLabel({ kind: "refund", id: "s1", code: "R-000007" })).toBe("Refund R-000007");
    expect(sourceLabel({ kind: "purchase_order", id: "po1", code: "PO-000014" })).toBe("Order PO-000014");
  });
});

describe("wording", () => {
  it("signs changes with a real minus sign", () => {
    expect(formatChange(12)).toBe("+12");
    expect(formatChange(-1500)).toBe("−1,500");
  });

  const summary: InventorySummary = {
    products: 1,
    units_on_hand: 1436,
    stock_value: "9781.40",
    currency: "PHP",
    low_stock: 0,
    out_of_stock: 2,
    people: [],
  };

  it("describes stock now, without comparisons", () => {
    const kpis = buildInventoryKpis(summary);
    expect(kpis.map((k) => [k.label, k.value, k.change])).toEqual([
      ["Stock value", "₱9,781", "At each product's current cost"],
      ["Units on hand", "1,436", "Across 1 product"],
      ["Low stock", "0", "Nothing at its reorder level"],
      ["Out of stock", "2", "None left to sell"],
    ]);
    expect(kpis.every((k) => k.trend === "neutral")).toBe(true);
  });
});

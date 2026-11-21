import { describe, expect, it } from "vitest";
import { adjustmentReasons, isProductSort, isStockStatus, movementReasonLabels } from "@/lib/products";

describe("URL param guards", () => {
  it("accepts only known stock statuses", () => {
    expect(isStockStatus("low_stock")).toBe(true);
    expect(isStockStatus("LOW_STOCK")).toBe(false);
    expect(isStockStatus("'; drop table products; --")).toBe(false);
    expect(isStockStatus(undefined)).toBe(false);
  });

  it("accepts only known sort keys", () => {
    expect(isProductSort("-stock")).toBe(true);
    expect(isProductSort("created_at")).toBe(false);
  });
});

describe("stock adjustment reasons", () => {
  it("matches the API's direction rules", () => {
    const direction = Object.fromEntries(adjustmentReasons.map((r) => [r.value, r.direction]));
    expect(direction).toEqual({
      purchase: "add",
      return: "add",
      damage: "remove",
      sale: "remove",
      adjustment: "either",
    });
  });

  it("never offers 'initial', which only the system sets", () => {
    expect(adjustmentReasons.map((r) => r.value)).not.toContain("initial");
  });

  it("has a readable label for every movement reason", () => {
    for (const label of Object.values(movementReasonLabels)) expect(label.length).toBeGreaterThan(0);
  });
});

import { describe, expect, it } from "vitest";
import type { Sale, SaleLine } from "@/lib/api/types";
import {
  canRefund,
  checkRefund,
  emptyDraft,
  fullDraft,
  leftToRefund,
  normalizeReceiptQuery,
  refundTotalCents,
} from "@/lib/sales";

const line = (id: string, quantity: number, refunded: number, price: string): SaleLine => ({
  id,
  product_id: `p-${id}`,
  product_name: `Item ${id}`,
  sku: id,
  unit: "pcs",
  unit_price: price,
  quantity,
  line_total: (Number(price) * quantity).toFixed(2),
  quantity_refunded: refunded,
});

// 3 noodles at 16.00 (1 already refunded), 2 sodas at 80.00, 1 fully refunded bread.
const sale = { lines: [line("a", 3, 1, "16.00"), line("b", 2, 0, "80.00"), line("c", 1, 1, "45.50")] } satisfies Pick<
  Sale,
  "lines"
>;

describe("what can be refunded", () => {
  it("counts what's left per line and hides fully refunded lines", () => {
    expect(sale.lines.map(leftToRefund)).toEqual([2, 2, 0]);
    expect(Object.keys(emptyDraft(sale))).toEqual(["a", "b"]);
    expect(emptyDraft(sale).a).toEqual({ quantity: "0", restock: true });
  });

  it("shows the Refund button only to managers, and only while something is left", () => {
    expect(canRefund(sale, true)).toBe(true);
    expect(canRefund(sale, false)).toBe(false);
    expect(canRefund({ lines: [line("c", 1, 1, "1.00")] }, true)).toBe(false);
  });

  it("'Refund everything' fills what's left and keeps restock choices", () => {
    const draft = fullDraft(sale, { a: { quantity: "0", restock: false }, b: { quantity: "1", restock: true } });
    expect(draft).toEqual({ a: { quantity: "2", restock: false }, b: { quantity: "2", restock: true } });
  });
});

describe("refund total", () => {
  it("adds valid lines in exact centavos and ignores invalid ones", () => {
    expect(refundTotalCents(sale, { a: { quantity: "2", restock: true }, b: { quantity: "1", restock: false } })).toBe(11200);
    expect(refundTotalCents(sale, { a: { quantity: "9", restock: true }, b: { quantity: "x", restock: true } })).toBe(0);
    expect(refundTotalCents(sale, { a: { quantity: "", restock: true } })).toBe(0);
  });
});

describe("checkRefund", () => {
  const draft = (a: string, b: string) => ({ a: { quantity: a, restock: true }, b: { quantity: b, restock: false } });

  it("returns only the lines with a quantity, ready for the API", () => {
    expect(checkRefund(sale, draft("1", "0"), "customer_return", "")).toEqual({
      ok: true,
      lines: [{ sale_line_id: "a", quantity: 1, restock: true }],
      totalCents: 1600,
      units: 1,
    });
  });

  it("explains every problem next to its field", () => {
    const result = checkRefund(sale, draft("3", "1.5"), "", "");
    expect(result).toEqual({
      ok: false,
      message: "Fix 3 problems to continue.",
      fields: { a: "Only 2 left to refund", b: "Enter a whole number", reason: "Choose a reason" },
    });
  });

  it("needs a note when the reason is Other", () => {
    expect(checkRefund(sale, draft("1", "0"), "other", "  ")).toMatchObject({
      ok: false,
      fields: { note: "Say why, since the reason is Other" },
    });
    expect(checkRefund(sale, draft("1", "0"), "other", "Promo price")).toMatchObject({ ok: true });
  });

  it("needs at least one item", () => {
    expect(checkRefund(sale, draft("0", ""), "damaged", "")).toEqual({
      ok: false,
      message: "Enter how many to refund for at least one item.",
      fields: {},
    });
  });
});

describe("normalizeReceiptQuery", () => {
  it.each([
    ["S-000123", "123"],
    ["s123", "123"],
    [" 000042 ", "42"],
    ["7", "7"],
  ])("reads %s as receipt %s", (input, expected) => {
    expect(normalizeReceiptQuery(input)).toBe(expected);
  });

  it("treats blank as no search and nonsense as an error", () => {
    expect(normalizeReceiptQuery(undefined)).toBeUndefined();
    expect(normalizeReceiptQuery("  ")).toBeUndefined();
    expect(normalizeReceiptQuery("R-000001")).toBeNull();
    expect(normalizeReceiptQuery("12a")).toBeNull();
  });
});

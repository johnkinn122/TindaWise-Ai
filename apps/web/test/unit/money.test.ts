import { describe, expect, it } from "vitest";
import { centsToDecimal, formatCents, quickCashAmounts, toCents } from "@/lib/money";

const plain = (value: string) => value.replace(/\u00a0|\u202f/g, " ");

describe("toCents", () => {
  it.each([
    ["16.00", 1600],
    ["16.5", 1650],
    ["200", 20000],
    ["1,000.25", 100025],
    ["0.1", 10],
  ])("%s → %d", (input, expected) => {
    expect(toCents(input)).toBe(expected);
  });

  it.each(["", "abc", "-5", "1.005", "1.2.3"])("rejects %s", (input) => {
    expect(toCents(input)).toBeNaN();
  });

  it("adds without float drift", () => {
    // 0.1 + 0.2 is 0.30000000000000004 in floats; in centavos it is exactly 30.
    expect(toCents("0.10") + toCents("0.20")).toBe(30);
  });
});

describe("formatting", () => {
  it("formats centavos as pesos", () => {
    expect(plain(formatCents(12800))).toBe("₱128.00");
    expect(centsToDecimal(7250)).toBe("72.50");
  });
});

describe("quickCashAmounts", () => {
  it("offers the exact amount, round-ups and common bills", () => {
    expect(quickCashAmounts(12800)).toEqual([12800, 14000, 15000, 20000, 50000]);
  });

  it("never offers less than the total", () => {
    for (const amount of quickCashAmounts(123456)) expect(amount).toBeGreaterThanOrEqual(123456);
  });

  it("offers nothing for an empty cart", () => {
    expect(quickCashAmounts(0)).toEqual([]);
  });
});

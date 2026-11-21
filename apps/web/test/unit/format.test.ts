import { describe, expect, it } from "vitest";
import { formatNumber, formatPercent, formatPeso, formatPesoWhole } from "@/lib/format";

// Intl may use a narrow no-break space in some locales; normalize so assertions read plainly.
const plain = (value: string) => value.replace(/ | /g, " ");

describe("formatPeso", () => {
  it("formats exact amounts with centavos", () => {
    expect(plain(formatPeso(1234.5))).toBe("₱1,234.50");
    expect(plain(formatPeso(0))).toBe("₱0.00");
  });

  it("formats headline amounts without centavos", () => {
    expect(plain(formatPesoWhole(18420))).toBe("₱18,420");
  });
});

describe("formatNumber", () => {
  it("adds thousands separators", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });
});

describe("formatPercent", () => {
  it("turns a ratio into a percentage", () => {
    expect(formatPercent(0.224)).toBe("22.4%");
    expect(formatPercent(0.15625, 2)).toBe("15.63%");
  });
});

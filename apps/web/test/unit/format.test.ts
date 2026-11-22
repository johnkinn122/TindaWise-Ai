import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatNumber, formatPercent, formatPeso, formatPesoWhole } from "@/lib/format";

// Intl may use a narrow no-break space in some locales; normalize so assertions read plainly.
const plain = (value: string) => value.replace(/ | /g, " ");

describe("formatDate and formatDateTime", () => {
  // 23:30 UTC on Saturday 21 Nov: already Sunday morning in Manila, still Saturday in Honolulu.
  const moment = "2026-11-21T23:30:00Z";

  it("show the moment in the store's time zone", () => {
    expect(formatDateTime(moment, "Asia/Manila")).toBe("Nov 22, 2026, 7:30 AM");
    expect(formatDateTime(moment, "Pacific/Honolulu")).toBe("Nov 21, 2026, 1:30 PM");
    expect(formatDate(moment, "Asia/Manila")).toBe("Nov 22, 2026");
    expect(formatDate(moment, "Pacific/Honolulu")).toBe("Nov 21, 2026");
  });

  it("reuse formatters across calls and zones without mixing them up", () => {
    const zones = ["Asia/Manila", "Europe/London", "Asia/Manila", "America/New_York"];
    expect(zones.map((zone) => formatDateTime(moment, zone))).toEqual([
      "Nov 22, 2026, 7:30 AM",
      "Nov 21, 2026, 11:30 PM",
      "Nov 22, 2026, 7:30 AM",
      "Nov 21, 2026, 6:30 PM",
    ]);
  });
});

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

import { describe, expect, it } from "vitest";
import { timeZoneOptions, utcOffset } from "@/lib/time-zones";

const JANUARY = new Date("2026-01-15T12:00:00Z");
const JULY = new Date("2026-07-15T12:00:00Z");

describe("utcOffset", () => {
  it("gives the offset in force at that moment", () => {
    expect(utcOffset("Asia/Manila", JANUARY)).toBe("GMT+8");
    expect(utcOffset("UTC", JANUARY)).toMatch(/^GMT(\+0)?$/); // runtimes differ
    expect(utcOffset("Asia/Kolkata", JANUARY)).toBe("GMT+5:30");
    // Daylight saving: New York is UTC-5 in winter and UTC-4 in summer.
    expect(utcOffset("America/New_York", JANUARY)).toBe("GMT-5");
    expect(utcOffset("America/New_York", JULY)).toBe("GMT-4");
  });
});

describe("timeZoneOptions", () => {
  const options = timeZoneOptions("Asia/Manila", JANUARY);

  it("lists every zone alphabetically with a readable label", () => {
    expect(options.length).toBeGreaterThan(300);
    const values = options.map((o) => o.value);
    expect(values).toEqual([...values].sort());
    expect(options.find((o) => o.value === "Asia/Manila")?.label).toBe("Asia/Manila (GMT+8)");
    expect(options.find((o) => o.value === "America/Los_Angeles")?.label).toBe("America/Los Angeles (GMT-8)");
  });

  it("always includes the saved zone, once", () => {
    const legacy = timeZoneOptions("Asia/Calcutta", JANUARY);
    expect(legacy.filter((o) => o.value === "Asia/Calcutta")).toHaveLength(1);
    expect(options.filter((o) => o.value === "Asia/Manila")).toHaveLength(1);
  });
});

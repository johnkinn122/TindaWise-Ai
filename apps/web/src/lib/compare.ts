/**
 * "Compared with" wording for KPI strips, shared by the Overview and Reports so both say it the
 * same way. Rules: no baseline means no percentage (never "+∞%"), and rounding to 0 says "Same".
 */

export type Trend = "up" | "down" | "neutral";

export interface Comparison {
  change: string;
  trend: Trend;
}

interface Wording {
  /** "last Sunday", "the previous 7 days" */
  against: string;
  /** Shown when the earlier period had nothing to compare with. */
  noBaseline: string;
}

/**
 * Whole-percent change of a count or amount (use centavos for money, so it's exact). Measured
 * against the size of the earlier value, so a loss shrinking toward profit reads as "up".
 */
export function percentChange(current: number, previous: number, wording: Wording): Comparison {
  if (previous === 0) return { change: wording.noBaseline, trend: "neutral" };
  const percent = Math.round(((current - previous) / Math.abs(previous)) * 100);
  if (percent === 0) return { change: `Same as ${wording.against}`, trend: "neutral" };
  return { change: `${Math.abs(percent)}% vs ${wording.against}`, trend: percent > 0 ? "up" : "down" };
}

/** Change of a ratio ("0.2240") in percentage points, one decimal. */
export function pointChange(
  current: string | null,
  previous: string | null,
  wording: Wording & { noCurrent: string },
): Comparison {
  if (current === null) return { change: wording.noCurrent, trend: "neutral" };
  if (previous === null) return { change: wording.noBaseline, trend: "neutral" };
  const points = Math.round((Number(current) - Number(previous)) * 1000) / 10;
  if (points === 0) return { change: `Same as ${wording.against}`, trend: "neutral" };
  return { change: `${Math.abs(points).toFixed(1)} pts vs ${wording.against}`, trend: points > 0 ? "up" : "down" };
}

/** Shared chart helpers (Recharts). */

const compactPesoFormatter = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  notation: "compact",
  maximumFractionDigits: 1,
});

/** "₱1.5K" for axis ticks. */
export const compactPeso = (value: number) => compactPesoFormatter.format(value);

/**
 * Y-axis ticks: five evenly spaced round numbers (0 and four steps) that cover `max`.
 * Steps are 1, 2, 2.5 or 5 times a power of ten, so labels stay readable.
 */
export function niceTicks(max: number): number[] {
  const rough = Math.max(max, 1) / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= rough) ?? 10 * magnitude;
  const safeStep = Math.max(step, 50); // an empty week still shows ₱0–₱200, not ₱0–₱1
  return [0, 1, 2, 3, 4].map((i) => i * safeStep);
}

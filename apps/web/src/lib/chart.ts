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
 * Y-axis ticks: evenly spaced round numbers that cover `min`..`max` and always include 0.
 * With nothing below zero that's five ticks (0 and four steps). Net sales can dip below zero on a
 * day with more refunds than sales; then the ticks start at the round step below `min`.
 * Steps are 1, 2, 2.5 or 5 times a power of ten, so labels stay readable.
 */
export function niceTicks(max: number, min = 0): number[] {
  const low = Math.min(min, 0);
  const high = Math.max(max, 0);
  const rough = Math.max(high - low, 1) / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= rough) ?? 10 * magnitude;
  const safeStep = Math.max(step, 50); // an empty week still shows ₱0–₱200, not ₱0–₱1
  if (low === 0) return [0, 1, 2, 3, 4].map((i) => i * safeStep);
  const ticks = [Math.floor(low / safeStep) * safeStep];
  while (ticks.at(-1)! < high) ticks.push(ticks.at(-1)! + safeStep);
  return ticks;
}

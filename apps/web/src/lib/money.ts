/**
 * Money math in whole centavos (integers), so ₱0.10 + ₱0.20 is exactly ₱0.30.
 * The API sends decimal strings ("16.00"); convert once, add integers, format at the end.
 * The server recomputes every total; these are for showing the cart while it's being built.
 */

/** "16.50" → 1650. Accepts what a person types ("200", "200.5", "1,000"). Returns NaN if invalid. */
export function toCents(value: string | number): number {
  const text = String(value).replace(/,/g, "").trim();
  if (!/^\d+(\.\d{0,2})?$/.test(text)) return Number.NaN;
  const [whole, fraction = ""] = text.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

/** 1650 → "16.50" (for sending to the API). */
export function centsToDecimal(cents: number): string {
  return (cents / 100).toFixed(2);
}

const peso = new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" });

/** 1650 → "₱16.50" */
export function formatCents(cents: number): string {
  return peso.format(cents / 100);
}

/**
 * Cash amounts a customer is likely to hand over for this total: the exact amount, the next
 * round ₱20/₱50/₱100, then common bills. Sorted, unique, all ≥ total.
 */
export function quickCashAmounts(totalCents: number): number[] {
  if (totalCents <= 0) return [];
  const roundUp = (step: number) => Math.ceil(totalCents / step) * step;
  const candidates = [totalCents, roundUp(2000), roundUp(5000), roundUp(10000), 50000, 100000];
  return [...new Set(candidates.filter((amount) => amount >= totalCents))].sort((a, b) => a - b).slice(0, 5);
}

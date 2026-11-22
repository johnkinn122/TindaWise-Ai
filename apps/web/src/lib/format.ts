/**
 * Locale-aware formatters. Tindawise defaults to Philippine peso (PHP) and en-PH.
 * Keep all number/currency formatting here so the whole UI stays consistent.
 */

const pesoFormatter = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  minimumFractionDigits: 2,
});

const pesoWholeFormatter = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("en-PH");

/** ₱1,234.50 — use for exact amounts (receipts, line items, totals). */
export function formatPeso(amount: number): string {
  return pesoFormatter.format(amount);
}

/** ₱18,420 — use for headline figures where centavos add noise. */
export function formatPesoWhole(amount: number): string {
  return pesoWholeFormatter.format(amount);
}

/** 1,234 */
export function formatNumber(value: number): string {
  return numberFormatter.format(value);
}

/** 22.4% — input is a ratio (0.224). */
export function formatPercent(ratio: number, fractionDigits = 1): string {
  return `${(ratio * 100).toFixed(fractionDigits)}%`;
}

const dateFormatter = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeZone: "Asia/Manila" });
const dateTimeFormatter = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Manila",
});
const calendarDateFormatter = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeZone: "UTC" });

/** "Nov 22, 2026" from a timestamp, in store time. */
export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

/** "Nov 22, 2026, 9:45 AM" from a timestamp, in store time. */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

/** "Nov 30, 2026" from a date with no time ("2026-11-30"), so no time zone can shift the day. */
export function formatCalendarDate(isoDate: string): string {
  return calendarDateFormatter.format(new Date(`${isoDate}T00:00:00Z`));
}

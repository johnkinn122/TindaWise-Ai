/**
 * Wording for the "Worth a look" panel. The rule that flags a day is in
 * services/api/app/services/anomalies.py; this file only explains it.
 */

import type { AnomalyAlert } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";

/** What happened, in the words an owner would use. A drop to zero gets its own name: it's the likeliest sign of sales not rung up. */
export function anomalyTitle(alert: Pick<AnomalyAlert, "kind" | "units_sold">): string {
  if (alert.kind === "spike") return "More sales than usual";
  return alert.units_sold === 0 ? "No sales recorded" : "Fewer sales than usual";
}

/** The evidence: "Sold 0 pcs while in stock · usually about 9 a day". */
export function anomalyDetail(alert: Pick<AnomalyAlert, "kind" | "units_sold" | "unit" | "usual_daily">): string {
  const sold = `Sold ${formatNumber(alert.units_sold)} ${alert.unit}`;
  const usual = `usually about ${formatNumber(Number(alert.usual_daily))} a day`;
  return alert.kind === "drop" ? `${sold} while in stock · ${usual}` : `${sold} · ${usual}`;
}

/** "2 sales days stand out in the last 7 days." */
export function anomalySummary(count: number): string {
  return count === 1
    ? "1 sales day stands out in the last 7 days."
    : `${formatNumber(count)} sales days stand out in the last 7 days.`;
}

/** Identifies an alert: one product, one store day, one direction. */
export function anomalyKey(alert: Pick<AnomalyAlert, "product_id" | "day" | "kind">): string {
  return `${alert.product_id}|${alert.day}|${alert.kind}`;
}

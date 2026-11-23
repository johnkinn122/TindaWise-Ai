/**
 * Wording for the "Worth a look" panel. The rules are in services/api/app/services/anomalies.py
 * (unusual sales days) and shrinkage.py (stock going missing); this file only explains them.
 */

import type { AnomalyAlert, StockLossAlert } from "@/lib/api/types";
import { formatCalendarDay, formatNumber, formatPercent } from "@/lib/format";

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

/** The evidence: "9 pcs missing in counts · 8.9% of 100 sold in 8 weeks". */
export function stockLossDetail(loss: Pick<StockLossAlert, "missing_units" | "unit" | "units_sold" | "missing_share">): string {
  const share = formatPercent(Number(loss.missing_share));
  return `${formatNumber(loss.missing_units)} ${loss.unit} missing in counts · ${share} of ${formatNumber(loss.units_sold)} sold in 8 weeks`;
}

/** "1 product lost 5% or more of its sales in stock counts over the last 8 weeks." */
export function stockLossSummary(count: number): string {
  return count === 1
    ? "1 product lost 5% or more of its sales in stock counts over the last 8 weeks."
    : `${formatNumber(count)} products lost 5% or more of their sales in stock counts over the last 8 weeks.`;
}

/** One row of the panel, whichever rule flagged it. `kind` and `day` identify it for dismissal. */
export interface WorthALookItem {
  product_id: string;
  name: string;
  day: string;
  kind: "spike" | "drop" | "shrinkage";
  title: string;
  /** "Sat, Nov 21" for a sales day; "Counted Fri, Nov 20" for stock going missing. */
  when: string;
  detail: string;
}

export function salesItem(alert: AnomalyAlert): WorthALookItem {
  return {
    product_id: alert.product_id,
    name: alert.name,
    day: alert.day,
    kind: alert.kind,
    title: anomalyTitle(alert),
    when: formatCalendarDay(alert.day),
    detail: anomalyDetail(alert),
  };
}

export function stockItem(loss: StockLossAlert): WorthALookItem {
  return {
    product_id: loss.product_id,
    name: loss.name,
    day: loss.day,
    kind: "shrinkage",
    title: "Missing in stock counts",
    when: `Counted ${formatCalendarDay(loss.day)}`,
    detail: stockLossDetail(loss),
  };
}

/** Identifies an alert: one product, one store day, one kind. */
export function anomalyKey(alert: Pick<WorthALookItem, "product_id" | "day" | "kind">): string {
  return `${alert.product_id}|${alert.day}|${alert.kind}`;
}

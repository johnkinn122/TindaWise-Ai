/**
 * Inventory page logic without fetching: reading the URL, links and wording.
 * Figures are defined in services/api/app/services/inventory_ledger.py; nothing is recomputed here.
 */

import type { InventorySummary, MovementReason, MovementSource } from "@/lib/api/types";
import { formatNumber, formatPesoWhole } from "@/lib/format";
import { toCents } from "@/lib/money";
import type { Kpi } from "@/lib/overview";
import { movementReasonLabels } from "@/lib/products";

export interface InventoryParams {
  q?: string;
  reason?: MovementReason;
  /** Who made the change (user id). */
  who?: string;
  /** One product (id), e.g. from a product page's "See all" link. */
  product?: string;
  start?: string;
  end?: string;
  page: number;
}

type RawParams = Record<string, string | string[] | undefined>;
const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const REASONS = Object.keys(movementReasonLabels) as MovementReason[];

/** Only well-formed values reach the API; anything else is dropped, as if it weren't there. */
export function parseInventoryParams(raw: RawParams): InventoryParams {
  const q = first(raw.q)?.trim().slice(0, 100);
  const reason = first(raw.reason);
  const who = first(raw.who);
  const product = first(raw.product);
  const start = first(raw.start);
  const end = first(raw.end);
  const page = Number.parseInt(first(raw.page) ?? "1", 10);
  return {
    ...(q && { q }),
    ...(REASONS.includes(reason as MovementReason) && { reason: reason as MovementReason }),
    ...(who && UUID.test(who) && { who }),
    ...(product && UUID.test(product) && { product }),
    ...(start && ISO_DATE.test(start) && { start }),
    ...(end && ISO_DATE.test(end) && { end }),
    page: Number.isFinite(page) && page > 1 ? page : 1,
  };
}

/** The filters as URL parameters (no page), for links that keep the current view. */
export function inventoryFilters(params: InventoryParams): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params).filter((entry): entry is [string, string] => entry[0] !== "page" && typeof entry[1] === "string" && entry[1] !== ""),
  );
}

export function hasFilters(params: InventoryParams): boolean {
  return Object.keys(inventoryFilters(params)).length > 0;
}

/** `/inventory?…` with `changes` applied (undefined removes a key). Changing a filter starts at page 1. */
export function inventoryHref(params: InventoryParams, changes: Partial<Record<keyof InventoryParams, string | undefined>> = {}) {
  const query = new URLSearchParams({ ...inventoryFilters(params) });
  for (const [key, value] of Object.entries(changes)) {
    if (value) query.set(key, value);
    else query.delete(key);
  }
  const text = query.toString();
  return text ? `/inventory?${text}` : "/inventory";
}

/** Refunds are shown on their receipt, so both open the sale. */
export function sourceHref(source: MovementSource): string {
  return source.kind === "purchase_order" ? `/purchase-orders/${source.id}` : `/sales/${source.id}`;
}

const sourceNouns: Record<MovementSource["kind"], string> = {
  sale: "Receipt",
  refund: "Refund",
  purchase_order: "Order",
};

/** "Receipt S-000123", "Refund R-000007", "Order PO-000004". */
export function sourceLabel(source: MovementSource): string {
  return `${sourceNouns[source.kind]} ${source.code}`;
}

/** "+12" or "−3" (a real minus sign, which screen readers read as minus). */
export function formatChange(change: number): string {
  return `${change > 0 ? "+" : "−"}${formatNumber(Math.abs(change))}`;
}

const plural = (count: number, one: string, many: string) => `${formatNumber(count)} ${count === 1 ? one : many}`;

/** Stock value, units, low and out of stock. These describe now, so nothing is compared. */
export function buildInventoryKpis(summary: InventorySummary): Kpi[] {
  return [
    {
      id: "stock-value",
      label: "Stock value",
      value: formatPesoWhole(toCents(summary.stock_value) / 100),
      change: "At each product's current cost",
      trend: "neutral",
    },
    {
      id: "units",
      label: "Units on hand",
      value: formatNumber(summary.units_on_hand),
      change: `Across ${plural(summary.products, "product", "products")}`,
      trend: "neutral",
    },
    {
      id: "low",
      label: "Low stock",
      value: formatNumber(summary.low_stock),
      change: summary.low_stock === 0 ? "Nothing at its reorder level" : "At or below the reorder level",
      trend: "neutral",
    },
    {
      id: "out",
      label: "Out of stock",
      value: formatNumber(summary.out_of_stock),
      change: summary.out_of_stock === 0 ? "Everything is on the shelf" : "None left to sell",
      trend: "neutral",
    },
  ];
}

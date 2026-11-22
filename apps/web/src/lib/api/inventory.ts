import "server-only";

import { apiFetch } from "./client";
import type { InventorySummary, LedgerEntry, Page } from "./types";
import type { InventoryParams } from "@/lib/inventory";

export const LEDGER_PAGE_SIZE = 25;

/** Every stock movement in the store, newest first. Owners and managers only (the API enforces it). */
export function listLedger(params: InventoryParams) {
  return apiFetch<Page<LedgerEntry>>("/inventory/movements", {
    query: {
      q: params.q,
      reason: params.reason,
      user_id: params.who,
      product_id: params.product,
      start: params.start,
      end: params.end,
      limit: LEDGER_PAGE_SIZE,
      offset: (params.page - 1) * LEDGER_PAGE_SIZE,
    },
  });
}

export function getInventorySummary(): Promise<InventorySummary> {
  return apiFetch<InventorySummary>("/inventory/summary");
}

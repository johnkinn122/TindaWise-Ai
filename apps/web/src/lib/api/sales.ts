import "server-only";

import { apiFetch } from "./client";
import type { Page, Sale, SaleSummary } from "./types";

export const SALES_PAGE_SIZE = 25;

/** Owners and managers get every sale; the API limits cashiers to their own. Newest first. */
export function listSales(params: { receipt?: string; page?: number }) {
  const page = Math.max(1, params.page ?? 1);
  const query = new URLSearchParams({
    limit: String(SALES_PAGE_SIZE),
    offset: String((page - 1) * SALES_PAGE_SIZE),
  });
  if (params.receipt) query.set("receipt", params.receipt);
  return apiFetch<Page<SaleSummary>>(`/sales?${query.toString()}`);
}

export function getSale(id: string): Promise<Sale> {
  return apiFetch<Sale>(`/sales/${encodeURIComponent(id)}`);
}

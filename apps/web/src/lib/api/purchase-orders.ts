import "server-only";

import { apiFetch } from "./client";
import type { Page, PurchaseOrder, PurchaseOrderStatus, PurchaseOrderSummary } from "./types";

export const PURCHASE_ORDERS_PAGE_SIZE = 25;

export function listPurchaseOrders(params: { statuses?: PurchaseOrderStatus[]; page?: number }) {
  const page = Math.max(1, params.page ?? 1);
  // Repeated ?status= values; apiFetch's query only takes single values, so build them here.
  const query = new URLSearchParams({
    limit: String(PURCHASE_ORDERS_PAGE_SIZE),
    offset: String((page - 1) * PURCHASE_ORDERS_PAGE_SIZE),
  });
  for (const status of params.statuses ?? []) query.append("status", status);
  return apiFetch<Page<PurchaseOrderSummary>>(`/purchase-orders?${query.toString()}`);
}

export function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  return apiFetch<PurchaseOrder>(`/purchase-orders/${encodeURIComponent(id)}`);
}

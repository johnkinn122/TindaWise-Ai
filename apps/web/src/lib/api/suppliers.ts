import "server-only";

import { apiFetch } from "./client";
import type { Page, Supplier } from "./types";

export function listSuppliers(params: { q?: string; includeArchived?: boolean } = {}): Promise<Page<Supplier>> {
  return apiFetch<Page<Supplier>>("/suppliers", {
    query: { q: params.q, include_archived: params.includeArchived, limit: 100 },
  });
}

export function getSupplier(id: string): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${encodeURIComponent(id)}`);
}

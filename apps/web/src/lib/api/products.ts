import "server-only";

import { apiFetch } from "./client";
import type { Category, Page, Product, ProductSort, StockMovement, StockStatus } from "./types";

export const PRODUCTS_PAGE_SIZE = 20;

export interface ProductListParams {
  q?: string;
  status?: StockStatus;
  categoryId?: string;
  sort?: ProductSort;
  page?: number;
}

export function listProducts(params: ProductListParams): Promise<Page<Product>> {
  const page = Math.max(1, params.page ?? 1);
  return apiFetch<Page<Product>>("/products", {
    query: {
      q: params.q,
      status: params.status,
      category_id: params.categoryId,
      sort: params.sort ?? "name",
      limit: PRODUCTS_PAGE_SIZE,
      offset: (page - 1) * PRODUCTS_PAGE_SIZE,
    },
  });
}

export function getProduct(id: string): Promise<Product> {
  return apiFetch<Product>(`/products/${encodeURIComponent(id)}`);
}

export function listCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/categories");
}

export function listMovements(productId: string, limit = 50): Promise<Page<StockMovement>> {
  return apiFetch<Page<StockMovement>>(`/products/${encodeURIComponent(productId)}/movements`, {
    query: { limit },
  });
}

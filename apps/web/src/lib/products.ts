/**
 * Product helpers that are safe on both server and client (no API access here).
 */
import type { MovementReason, ProductSort, StockStatus } from "@/lib/api/types";

export const stockStatusOptions: { value: StockStatus; label: string }[] = [
  { value: "in_stock", label: "In stock" },
  { value: "low_stock", label: "Low stock" },
  { value: "out_of_stock", label: "Out of stock" },
];

export const sortOptions: { value: ProductSort; label: string }[] = [
  { value: "name", label: "Name (A–Z)" },
  { value: "-name", label: "Name (Z–A)" },
  { value: "stock", label: "Stock (lowest first)" },
  { value: "-stock", label: "Stock (highest first)" },
  { value: "-price", label: "Price (highest first)" },
  { value: "price", label: "Price (lowest first)" },
  { value: "-updated", label: "Recently updated" },
];

/** Reasons a person can record by hand, with the direction each one moves stock. */
export const adjustmentReasons: { value: MovementReason; label: string; direction: "add" | "remove" | "either" }[] = [
  { value: "purchase", label: "Received from supplier", direction: "add" },
  { value: "return", label: "Customer return", direction: "add" },
  { value: "damage", label: "Damaged or expired", direction: "remove" },
  { value: "sale", label: "Sold (manual entry)", direction: "remove" },
  { value: "adjustment", label: "Stock count correction", direction: "either" },
];

export const movementReasonLabels: Record<MovementReason, string> = {
  initial: "Opening stock",
  purchase: "Received from supplier",
  sale: "Sold",
  return: "Customer return",
  damage: "Damaged or expired",
  adjustment: "Stock count correction",
};

export function isStockStatus(value: unknown): value is StockStatus {
  return stockStatusOptions.some((option) => option.value === value);
}

export function isProductSort(value: unknown): value is ProductSort {
  return sortOptions.some((option) => option.value === value);
}

/**
 * SAMPLE DATA — for UI development only.
 *
 * Nothing in this file comes from a real store, a database, or a trained model.
 * It exists so the Overview screen can be designed before the FastAPI backend
 * (services/api) and the forecasting service (services/ml) are built.
 * Every screen that reads from here must show the "Sample data" label.
 * Replace these exports with API calls once the backend exists.
 */

import type { StockStatus } from "@/lib/api/types";

export type { StockStatus };

export interface Kpi {
  id: string;
  label: string;
  value: string;
  /** Short comparison line, e.g. "12% vs last Saturday". */
  change: string;
  trend: "up" | "down" | "neutral";
}

export interface DailySales {
  day: string;
  thisWeek: number | null;
  lastWeek: number;
  /** Forecast only exists for days that have not happened yet (plus the joining day). */
  forecast: number | null;
}

export interface StockItem {
  id: string;
  name: string;
  category: string;
  onHand: number;
  status: StockStatus;
}

export interface ReorderLine {
  productId: string;
  name: string;
  quantity: number;
  unit: string;
  unitCost: number;
}

export interface ReorderSuggestion {
  id: string;
  title: string;
  reason: string;
  lines: ReorderLine[];
  basis: string;
  supplier: string;
}

export const sampleKpis: Kpi[] = [
  { id: "sales", label: "Sales today", value: "₱18,420", change: "12% vs last Friday", trend: "up" },
  { id: "transactions", label: "Transactions", value: "214", change: "9% vs last Friday", trend: "up" },
  { id: "margin", label: "Gross margin", value: "22.4%", change: "1.1 pts vs last week", trend: "down" },
  { id: "low-stock", label: "Items running low", value: "7", change: "3 out of stock", trend: "neutral" },
];

export const sampleWeeklySales: DailySales[] = [
  { day: "Sun", thisWeek: 12800, lastWeek: 11400, forecast: null },
  { day: "Mon", thisWeek: 14100, lastWeek: 12300, forecast: null },
  { day: "Tue", thisWeek: 13600, lastWeek: 11900, forecast: null },
  { day: "Wed", thisWeek: 15900, lastWeek: 13800, forecast: null },
  { day: "Thu", thisWeek: 16700, lastWeek: 14500, forecast: null },
  { day: "Fri", thisWeek: 18420, lastWeek: 16450, forecast: 18420 },
  { day: "Sat", thisWeek: null, lastWeek: 16900, forecast: 21000 },
];

export const sampleStockToWatch: StockItem[] = [
  { id: "p-001", name: "Lucky Me Pancit Canton (Original)", category: "Noodles", onHand: 6, status: "low_stock" },
  { id: "p-002", name: "Coca-Cola 1.5L", category: "Beverages", onHand: 0, status: "out_of_stock" },
  { id: "p-003", name: "Bear Brand Swak 33g", category: "Dairy", onHand: 4, status: "low_stock" },
  { id: "p-004", name: "Datu Puti Vinegar 1L", category: "Condiments", onHand: 38, status: "in_stock" },
];

export const sampleReorderSuggestion: ReorderSuggestion = {
  id: "rs-001",
  title: "Restock 3 items before Monday",
  reason: "Payday weekend demand is usually about 30% higher. These items are likely to run out by Sunday afternoon.",
  lines: [
    { productId: "p-001", name: "Lucky Me Pancit Canton", quantity: 48, unit: "pcs", unitCost: 14.5 },
    { productId: "p-002", name: "Coca-Cola 1.5L", quantity: 24, unit: "btl", unitCost: 68 },
    { productId: "p-003", name: "Bear Brand Swak 33g", quantity: 36, unit: "pcs", unitCost: 15.25 },
  ],
  basis: "Based on 90 days of sales",
  supplier: "Puregold Wholesale",
};

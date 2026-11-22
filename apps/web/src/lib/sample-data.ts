/**
 * SAMPLE DATA — for UI development only.
 *
 * Nothing in this file comes from a real store, a database, or a trained model.
 * The Overview now uses real data (lib/overview.ts). What remains is the AI reorder suggestion
 * behind the Resibo card, kept until the forecasting service (services/ml) exists.
 * Any screen that renders it must show the "Sample data" label.
 */

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

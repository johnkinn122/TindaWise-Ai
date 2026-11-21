/**
 * Types mirroring the Tindawise API (services/api/app/schemas).
 * Money arrives as a decimal string ("16.00") to avoid float rounding; parse only for display.
 */

export type StockStatus = "in_stock" | "low_stock" | "out_of_stock";

export type MovementReason = "initial" | "purchase" | "sale" | "return" | "damage" | "adjustment";

export type ProductSort = "name" | "-name" | "stock" | "-stock" | "price" | "-price" | "-updated";

export interface Category {
  id: string;
  name: string;
}

export interface Product {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  category: Category | null;
  unit: string;
  price: string;
  cost: string;
  currency: string;
  stock_on_hand: number;
  reorder_level: number;
  stock_status: StockStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockMovement {
  id: string;
  product_id: string;
  quantity_change: number;
  balance_after: number;
  reason: MovementReason;
  note: string | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    fields: Record<string, string>;
  };
}

export interface SaleLine {
  product_id: string;
  product_name: string;
  sku: string;
  unit: string;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface Sale {
  id: string;
  receipt_number: number;
  receipt_code: string;
  total: string;
  currency: string;
  payment_method: "cash" | "e_wallet";
  amount_tendered: string | null;
  change_due: string | null;
  payment_reference: string | null;
  created_at: string;
  cashier_name: string | null;
  item_count: number;
  lines: SaleLine[];
}

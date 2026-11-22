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
  /** Null for cashiers: the API doesn't send costs to roles that may not see them. */
  cost: string | null;
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

/** GET /overview. Money is a decimal string; gross_margin is a ratio string ("0.2240"). */
export interface SalesFigures {
  sales: string;
  transactions: number;
  /** Null when there were no sales, or for roles that may not see costs. */
  gross_margin: string | null;
}

export interface OverviewDay {
  /** Calendar date in the store's time zone, e.g. "2026-11-22". */
  date: string;
  /** Null for days that haven't happened yet. */
  sales: string | null;
  last_week_sales: string;
}

export interface StockWatchItem {
  id: string;
  name: string;
  category: string | null;
  unit: string;
  stock_on_hand: number;
  reorder_level: number;
  stock_status: StockStatus;
}

export interface ReorderLine {
  product_id: string;
  name: string;
  unit: string;
  stock_on_hand: number;
  reorder_level: number;
  sold_recently: number;
  suggested_quantity: number;
  unit_cost: string | null;
}

export interface Overview {
  as_of: string;
  timezone: string;
  currency: string;
  /** "mine" for cashiers: sales figures cover their own sales only. */
  sales_scope: "store" | "mine";
  costs_visible: boolean;
  today: SalesFigures;
  same_day_last_week: SalesFigures;
  /** Sunday to Saturday of the current week. */
  week: OverviewDay[];
  low_stock_count: number;
  out_of_stock_count: number;
  stock_to_watch: StockWatchItem[];
  reorder: {
    lines: ReorderLine[];
    total_count: number;
    lookback_days: number;
    estimated_cost: string | null;
  };
}

export interface Supplier {
  id: string;
  name: string;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type PurchaseOrderStatus = "draft" | "approved" | "partially_received" | "received" | "closed" | "cancelled";

export interface PurchaseOrderSummary {
  id: string;
  /** "PO-000001" */
  code: string;
  status: PurchaseOrderStatus;
  /** Null only on drafts that don't have a supplier yet. */
  supplier: { id: string; name: string; is_active: boolean } | null;
  total: string;
  currency: string;
  line_count: number;
  /** "2026-11-30" */
  expected_on: string | null;
  created_at: string;
}

export interface PurchaseOrderLine {
  id: string;
  product_id: string;
  product_name: string;
  sku: string;
  unit: string;
  quantity_ordered: number;
  quantity_received: number;
  quantity_remaining: number;
  unit_cost: string;
  line_total: string;
}

export interface PurchaseOrderReceipt {
  id: string;
  note: string | null;
  created_at: string;
  received_by: string | null;
  lines: { product_id: string; product_name: string; quantity: number }[];
}

export interface PurchaseOrder extends PurchaseOrderSummary {
  notes: string | null;
  lines: PurchaseOrderLine[];
  receipts: PurchaseOrderReceipt[];
  history: { action: "created" | "approved" | "received" | "closed" | "cancelled"; at: string; by: string | null }[];
  updated_at: string;
}

export type ReportPreset = "today" | "yesterday" | "last_7_days" | "last_30_days" | "this_month" | "last_month";
export type ReportProductSort = "sales" | "gross_profit" | "quantity";

export interface ReportPeriod {
  /** Store-local calendar days, both included: "2026-11-16". */
  start: string;
  end: string;
  days: number;
}

export interface ReportSummary {
  sales: string;
  transactions: number;
  average_sale: string | null;
  gross_profit: string;
  /** Ratio string ("0.2240"); null with no sales. */
  gross_margin: string | null;
  items_sold: number;
}

/** GET /reports/sales (owners and managers). */
export interface SalesReport {
  timezone: string;
  currency: string;
  period: ReportPeriod;
  previous_period: ReportPeriod;
  granularity: "day" | "week" | "month";
  summary: ReportSummary;
  previous_summary: ReportSummary;
  /** One point per day/week/month, zero-filled; `start` is the bucket's first day. */
  series: { start: string; sales: string; transactions: number; gross_profit: string }[];
  products: {
    product_id: string;
    name: string;
    sku: string;
    unit: string;
    quantity: number;
    sales: string;
    gross_profit: string;
    gross_margin: string | null;
  }[];
  product_count: number;
  product_sort: ReportProductSort;
  categories: { category_id: string | null; name: string; quantity: number; sales: string; gross_profit: string }[];
  payments: { method: "cash" | "e_wallet"; sales: string; transactions: number }[];
  suppliers: { supplier_id: string; name: string; received_value: string; deliveries: number }[];
  purchases_total: string;
}

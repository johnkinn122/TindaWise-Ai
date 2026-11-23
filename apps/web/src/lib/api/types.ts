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
  id: string;
  product_id: string;
  product_name: string;
  sku: string;
  unit: string;
  unit_price: string;
  quantity: number;
  line_total: string;
  quantity_refunded: number;
}

export type RefundReason = "customer_return" | "damaged" | "wrong_item" | "other";
export type RefundStatus = "none" | "partial" | "full";

/** Money given back on a receipt. No cost fields: cashiers can read refunds on their receipts. */
export interface Refund {
  id: string;
  refund_number: number;
  /** "R-000001" */
  refund_code: string;
  total: string;
  /** Paid back the way the sale was paid. */
  payment_method: "cash" | "e_wallet";
  reason: RefundReason;
  note: string | null;
  created_at: string;
  refunded_by_name: string | null;
  lines: {
    sale_line_id: string;
    product_id: string;
    product_name: string;
    unit: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    /** False: damaged or spoiled, not put back in stock. */
    restocked: boolean;
  }[];
}

export interface SaleSummary {
  id: string;
  receipt_number: number;
  receipt_code: string;
  total: string;
  refunded_total: string;
  refund_status: RefundStatus;
  payment_method: "cash" | "e_wallet";
  created_at: string;
  cashier_name: string | null;
  item_count: number;
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
  refunded_total: string;
  refund_status: RefundStatus;
  created_at: string;
  cashier_name: string | null;
  item_count: number;
  lines: SaleLine[];
  refunds: Refund[];
}

/** GET /overview. Money is a decimal string; gross_margin is a ratio string ("0.2240"). */
export interface SalesFigures {
  /** Net: sales rung up minus refunds given that day. Can be negative. */
  sales: string;
  /** Refunds given that day, already subtracted from `sales`. */
  refunds: string;
  transactions: number;
  /** Null when there were no sales, or for roles that may not see costs. */
  gross_margin: string | null;
}

export interface OverviewDay {
  /** Calendar date in the store's time zone, e.g. "2026-11-22". */
  date: string;
  /** Net sales (can be negative). Null for days that haven't happened yet. */
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
  /** Units on open purchase orders (draft, approved, partly received). */
  on_order: number;
  reorder_level: number;
  suggested_quantity: number;
  /** "recent_sales": from daily_rate; "reorder_level": too little history for a rate. */
  basis: "recent_sales" | "reorder_level";
  /** Units a day on in-stock days, one decimal. Null when the reorder level was used. */
  daily_rate: string | null;
  in_stock_days: number;
  lead_time_days: number;
  lead_time_source: "supplier" | "store_default";
  supplier_name: string | null;
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
    /** Days of sales history the daily rates come from. */
    window_days: number;
    /** Days of sales each order covers beyond the delivery time. */
    cover_days: number;
    estimated_cost: string | null;
  };
}

export type AuditAction =
  | "store.updated"
  | "member.added"
  | "refund.created"
  | "purchase_order.approved"
  | "purchase_order.cancelled"
  | "purchase_order.closed"
  | "product.price_changed"
  | "product.archived"
  | "anomaly.dismissed";

/**
 * One unusual sales day (GET /anomalies, owners and managers). The rule is in
 * services/api/app/services/anomalies.py.
 */
export interface AnomalyAlert {
  product_id: string;
  name: string;
  sku: string;
  unit: string;
  /** Store-local calendar day ("2026-11-21"). */
  day: string;
  /** "spike": sold far more than usual. "drop": sold far less than usual while in stock. */
  kind: "spike" | "drop";
  units_sold: number;
  /** Average units a day on recent in-stock days, one decimal ("9.0"). */
  usual_daily: string;
  in_stock_days: number;
}

export interface Anomalies {
  as_of: string;
  timezone: string;
  /** The days checked: the 7 complete store days before today. */
  first_day: string;
  last_day: string;
  window_days: number;
  spike_multiple: string;
  drop_multiple: string;
  /** Not dismissed, newest day first. */
  alerts: AnomalyAlert[];
  dismissed_count: number;
}

/** One entry of the append-only activity log (GET /audit-events, owner only). */
export interface AuditEvent {
  id: string;
  action: AuditAction;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  details: Record<string, unknown>;
  actor_user_id: string | null;
  actor_name: string | null;
  created_at: string;
}

/** Store settings (GET/PATCH /store). Currency is shown but can't be changed. */
export interface Store {
  id: string;
  name: string;
  currency: string;
  timezone: string;
  default_lead_time_days: number;
  updated_at: string;
}

export interface Supplier {
  id: string;
  name: string;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
  /** Days from ordering to delivery; null means the store default is used. */
  lead_time_days: number | null;
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

/** Sales figures are net of refunds (and can be negative) unless the name says gross. */
export interface ReportSummary {
  gross_sales: string;
  /** Refunds given in the period, whatever the sale date. */
  refunds: string;
  refund_count: number;
  /** Net: gross_sales - refunds. */
  sales: string;
  transactions: number;
  /** gross_sales / transactions; null with no sales. */
  average_sale: string | null;
  gross_profit: string;
  /** Ratio string ("0.2240"); null when net sales are zero or less. */
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
  series: { start: string; sales: string; refunds: string; transactions: number; gross_profit: string }[];
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
  payments: { method: "cash" | "e_wallet"; sales: string; refunds: string; transactions: number }[];
  suppliers: { supplier_id: string; name: string; received_value: string; deliveries: number }[];
  purchases_total: string;
}

// ── Inventory ledger (GET /inventory/...) ───────────────────────────────────

export type MovementSourceKind = "sale" | "refund" | "purchase_order";

/** What caused a movement. `id` is the page to open: the receipt for a sale or refund, the order for a delivery. */
export interface MovementSource {
  kind: MovementSourceKind;
  id: string;
  code: string;
}

export interface LedgerEntry {
  id: string;
  created_at: string;
  product_id: string;
  product_name: string;
  sku: string;
  unit: string;
  quantity_change: number;
  balance_after: number;
  reason: MovementReason;
  note: string | null;
  created_by_name: string | null;
  source: MovementSource | null;
}

export interface Person {
  id: string;
  name: string;
}

/** Active products only. `stock_value` is units on hand × each product's current cost. */
export interface InventorySummary {
  products: number;
  units_on_hand: number;
  stock_value: string;
  currency: string;
  low_stock: number;
  out_of_stock: number;
  people: Person[];
}

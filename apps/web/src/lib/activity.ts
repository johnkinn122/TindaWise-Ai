/**
 * Activity log logic without fetching: reading the URL, action names and links to records.
 * What is recorded is defined in services/api/app/models/audit_event.py.
 */

import type { AuditAction, AuditEvent } from "@/lib/api/types";

export const ACTIVITY_PAGE_SIZE = 25;

export const actionLabels: Record<AuditAction, string> = {
  "store.updated": "Store settings changed",
  "member.added": "Team member added",
  "refund.created": "Refund given",
  "purchase_order.approved": "Purchase order approved",
  "purchase_order.cancelled": "Purchase order cancelled",
  "purchase_order.closed": "Purchase order closed short",
  "product.price_changed": "Price or cost changed",
  "product.archived": "Product archived",
};

const ACTIONS = Object.keys(actionLabels) as AuditAction[];

export interface ActivityParams {
  action?: AuditAction;
  page: number;
}

type RawParams = Record<string, string | string[] | undefined>;
const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

/** Only known actions and positive pages reach the API; anything else is ignored. */
export function parseActivityParams(raw: RawParams): ActivityParams {
  const action = first(raw.action);
  const page = Number.parseInt(first(raw.page) ?? "1", 10);
  return {
    ...(ACTIONS.includes(action as AuditAction) && { action: action as AuditAction }),
    page: Number.isFinite(page) && page > 1 ? page : 1,
  };
}

/** The API's query for these params. */
export function activityQuery(params: ActivityParams): Record<string, string> {
  return {
    ...(params.action && { action: params.action }),
    limit: String(ACTIVITY_PAGE_SIZE),
    offset: String((params.page - 1) * ACTIVITY_PAGE_SIZE),
  };
}

/** Where the record an event is about lives in the app, if it has a page. */
export function activityLink(event: AuditEvent): { href: string; label: string } | null {
  switch (event.entity_type) {
    case "refund": {
      const saleId = typeof event.details.sale_id === "string" ? event.details.sale_id : null;
      return saleId ? { href: `/sales/${saleId}`, label: "Open receipt" } : null;
    }
    case "purchase_order":
      return event.entity_id ? { href: `/purchase-orders/${event.entity_id}`, label: "Open order" } : null;
    case "product":
      return event.entity_id ? { href: `/products/${event.entity_id}`, label: "Open product" } : null;
    case "user":
      return { href: "/settings/team", label: "Open team" };
    case "store":
      return { href: "/settings/store", label: "Open settings" };
    default:
      return null;
  }
}

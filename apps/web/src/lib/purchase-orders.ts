/**
 * Purchase order rules for the UI: status wording, list filters, and which actions to offer.
 * The API enforces every rule; this only decides what to show, so nobody is offered a button
 * that would be refused. Keep in sync with services/api/app/services/purchase_orders.py.
 */

import type { PurchaseOrder, PurchaseOrderStatus } from "@/lib/api/types";
import type { Role } from "@/lib/auth/current-user";

export const statusLabels: Record<PurchaseOrderStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  partially_received: "Partly received",
  received: "Received",
  closed: "Closed short",
  cancelled: "Cancelled",
};

/** List tabs. Each maps to one or more statuses; "all" has none. */
export const statusFilters = [
  { id: "all", label: "All", statuses: [] },
  { id: "draft", label: "Drafts", statuses: ["draft"] },
  { id: "open", label: "To receive", statuses: ["approved", "partially_received"] },
  { id: "done", label: "Done", statuses: ["received", "closed"] },
  { id: "cancelled", label: "Cancelled", statuses: ["cancelled"] },
] as const satisfies readonly { id: string; label: string; statuses: readonly PurchaseOrderStatus[] }[];

export type StatusFilterId = (typeof statusFilters)[number]["id"];

export function findStatusFilter(id: string | undefined) {
  return statusFilters.find((filter) => filter.id === id) ?? statusFilters[0];
}

export interface PurchaseOrderActions {
  edit: boolean;
  approve: boolean;
  receive: boolean;
  closeShort: boolean;
  cancel: boolean;
}

/**
 * - Owners and managers edit drafts, receive deliveries and close part-delivered orders.
 * - Only the owner approves, and only the owner cancels an approved order.
 * - Nothing that has stock received against it can be cancelled.
 */
export function availableActions(po: Pick<PurchaseOrder, "status">, role: Role): PurchaseOrderActions {
  const staff = role === "owner" || role === "manager";
  const owner = role === "owner";
  return {
    edit: staff && po.status === "draft",
    approve: owner && po.status === "draft",
    receive: staff && (po.status === "approved" || po.status === "partially_received"),
    closeShort: staff && po.status === "partially_received",
    cancel: (staff && po.status === "draft") || (owner && po.status === "approved"),
  };
}

/** Why the approve step is blocked, in plain words, or null when it can go ahead. */
export function approvalBlocker(po: Pick<PurchaseOrder, "status" | "supplier">): string | null {
  if (po.status !== "draft") return null;
  if (!po.supplier) return "Choose a supplier before this order can be approved.";
  if (!po.supplier.is_active) return `${po.supplier.name} is archived. Choose another supplier.`;
  return null;
}

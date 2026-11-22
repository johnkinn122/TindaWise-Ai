"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
import type { PurchaseOrder } from "@/lib/api/types";
import { type FormState, toFormState } from "@/lib/form-state";

/**
 * Server Actions for purchase orders. The API enforces every rule (roles, statuses, quantities);
 * these pass the request through and turn refusals into messages the page can show.
 */

export interface DraftInput {
  supplier_id: string | null;
  expected_on: string | null;
  notes: string | null;
  lines: { product_id: string; quantity: number; unit_cost: string }[];
}

const path = (id: string, action = "") => `/purchase-orders/${encodeURIComponent(id)}${action}`;

/** Create (no id) or update a draft, then open it. The key makes a double submit create one draft. */
export async function saveDraftAction(poId: string | null, input: DraftInput, idempotencyKey: string): Promise<FormState> {
  let po: PurchaseOrder;
  try {
    po = poId
      ? await apiFetch<PurchaseOrder>(path(poId), { method: "PATCH", body: input })
      : await apiFetch<PurchaseOrder>("/purchase-orders", {
          method: "POST",
          body: input,
          headers: { "Idempotency-Key": idempotencyKey },
        });
  } catch (error) {
    return toFormState(error);
  }
  redirect(`/purchase-orders/${po.id}`);
}

/** The Overview's "Create purchase order": a draft from the reorder suggestions, opened for review. */
export async function createFromReorderAction(idempotencyKey: string): Promise<FormState> {
  let po: PurchaseOrder;
  try {
    po = await apiFetch<PurchaseOrder>("/purchase-orders/from-reorder", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    });
  } catch (error) {
    return toFormState(error);
  }
  redirect(`/purchase-orders/${po.id}/edit`);
}

async function statusChange(poId: string, action: "/approve" | "/cancel" | "/close"): Promise<FormState> {
  try {
    await apiFetch<PurchaseOrder>(path(poId, action), { method: "POST" });
  } catch (error) {
    return toFormState(error);
  }
  refresh();
  return { status: "success" };
}

export async function approveAction(poId: string) {
  return statusChange(poId, "/approve");
}

export async function cancelAction(poId: string) {
  return statusChange(poId, "/cancel");
}

export async function closeShortAction(poId: string) {
  return statusChange(poId, "/close");
}

/** One delivery. The key is kept for retries of the same delivery, so stock is added once. */
export async function receiveAction(
  poId: string,
  lines: { line_id: string; quantity: number }[],
  note: string,
  idempotencyKey: string,
): Promise<FormState> {
  try {
    await apiFetch<PurchaseOrder>(path(poId, "/receive"), {
      method: "POST",
      body: { lines, note: note.trim() || null },
      headers: { "Idempotency-Key": idempotencyKey },
    });
  } catch (error) {
    return toFormState(error);
  }
  refresh();
  return { status: "success", message: "Delivery recorded. Stock and costs are updated." };
}

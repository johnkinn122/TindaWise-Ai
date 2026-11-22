"use server";

import { redirect } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
import type { RefundReason, Sale } from "@/lib/api/types";
import { type FormState, toFormState } from "@/lib/form-state";

export interface RefundInput {
  lines: { sale_line_id: string; quantity: number; restock: boolean }[];
  reason: RefundReason;
  note: string;
}

/**
 * Give a refund, then open the receipt showing it. Amounts aren't sent: the API takes them from the
 * receipt. The key is kept by the form until this succeeds, so a retry can't pay out twice.
 */
export async function refundAction(saleId: string, input: RefundInput, idempotencyKey: string): Promise<FormState> {
  let sale: Sale;
  try {
    sale = await apiFetch<Sale>(`/sales/${encodeURIComponent(saleId)}/refunds`, {
      method: "POST",
      body: { lines: input.lines, reason: input.reason, note: input.note.trim() || null },
      headers: { "Idempotency-Key": idempotencyKey },
    });
  } catch (error) {
    return toFormState(error);
  }
  const latest = sale.refunds.at(-1);
  redirect(`/sales/${sale.id}${latest ? `?refunded=${encodeURIComponent(latest.refund_code)}` : ""}`);
}

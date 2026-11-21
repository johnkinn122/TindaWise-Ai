"use server";

import { refresh } from "next/cache";
import { ApiError, ApiUnavailableError, apiFetch } from "@/lib/api/client";
import type { Sale } from "@/lib/api/types";

export interface CheckoutInput {
  lines: { product_id: string; quantity: number }[];
  payment_method: "cash" | "e_wallet";
  amount_tendered?: string;
  payment_reference?: string;
  /** One key per checkout attempt; a retry with the same key can't record twice. */
  idempotency_key: string;
}

export type CheckoutResult =
  | { status: "success"; sale: Sale }
  | { status: "error"; message: string; fields: Record<string, string> };

export async function checkoutAction(input: CheckoutInput): Promise<CheckoutResult> {
  try {
    // Prices aren't sent: the API reads them from the database and computes the total.
    const sale = await apiFetch<Sale>("/sales", {
      method: "POST",
      body: {
        lines: input.lines,
        payment_method: input.payment_method,
        amount_tendered: input.payment_method === "cash" ? input.amount_tendered : undefined,
        payment_reference: input.payment_method === "e_wallet" ? input.payment_reference : undefined,
      },
      headers: { "Idempotency-Key": input.idempotency_key },
    });
    refresh();
    return { status: "success", sale };
  } catch (error) {
    if (error instanceof ApiError) return { status: "error", message: error.message, fields: error.fields };
    if (error instanceof ApiUnavailableError) {
      return {
        status: "error",
        message: "Can't reach Tindawise right now. The sale was not recorded. Try again.",
        fields: {},
      };
    }
    throw error;
  }
}

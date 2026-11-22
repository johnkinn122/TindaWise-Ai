/**
 * Sales history and refund rules without fetching, so they're unit-tested. The API applies the
 * same rules again (and locks the receipt); these only give fast, specific feedback in the form.
 */

import type { RefundReason, RefundStatus, Sale, SaleLine } from "@/lib/api/types";
import { toCents } from "@/lib/money";

export const refundReasons: { id: RefundReason; label: string; hint: string }[] = [
  { id: "customer_return", label: "Customer returned it", hint: "Unused, or they changed their mind" },
  { id: "damaged", label: "Damaged or spoiled", hint: "Defective, expired or broken" },
  { id: "wrong_item", label: "Rung up by mistake", hint: "Wrong item or quantity at the counter" },
  { id: "other", label: "Other", hint: "Say why in the note" },
];

export const refundReasonLabels = Object.fromEntries(refundReasons.map((r) => [r.id, r.label])) as Record<
  RefundReason,
  string
>;

export const refundStatusLabels: Record<RefundStatus, string> = {
  none: "Paid",
  partial: "Partly refunded",
  full: "Refunded",
};

export const paymentMethodLabels: Record<Sale["payment_method"], string> = {
  cash: "Cash",
  e_wallet: "E-wallet",
};

/** How the money goes back, in the confirmation: "in cash" / "to the customer's e-wallet". */
export const payBackWording: Record<Sale["payment_method"], string> = {
  cash: "in cash",
  e_wallet: "to the customer's e-wallet",
};

export const leftToRefund = (line: Pick<SaleLine, "quantity" | "quantity_refunded">) =>
  line.quantity - line.quantity_refunded;

/** The Refund button shows for owners and managers while anything on the receipt is left. */
export function canRefund(sale: Pick<Sale, "lines">, canManage: boolean): boolean {
  return canManage && sale.lines.some((line) => leftToRefund(line) > 0);
}

export interface RefundDraftLine {
  /** As typed. Blank means 0. */
  quantity: string;
  /** Put back on the shelf (stock goes up). */
  restock: boolean;
}

export type RefundDraft = Record<string, RefundDraftLine>;

/** Every refundable line at 0, restocking on (the common case: the item is fine). */
export function emptyDraft(sale: Pick<Sale, "lines">): RefundDraft {
  return Object.fromEntries(
    sale.lines.filter((line) => leftToRefund(line) > 0).map((line) => [line.id, { quantity: "0", restock: true }]),
  );
}

/** Every unit that's left, for "Refund everything". Keeps each line's restock choice. */
export function fullDraft(sale: Pick<Sale, "lines">, current: RefundDraft): RefundDraft {
  return Object.fromEntries(
    sale.lines
      .filter((line) => leftToRefund(line) > 0)
      .map((line) => [line.id, { quantity: String(leftToRefund(line)), restock: current[line.id]?.restock ?? true }]),
  );
}

const parseQuantity = (raw: string): number => {
  const text = raw.trim() || "0";
  return /^\d{1,5}$/.test(text) ? Number(text) : Number.NaN;
};

/** The refund total so far, in centavos. Lines with invalid or too-large quantities count as 0. */
export function refundTotalCents(sale: Pick<Sale, "lines">, draft: RefundDraft): number {
  return sale.lines.reduce((sum, line) => {
    const quantity = parseQuantity(draft[line.id]?.quantity ?? "0");
    if (Number.isNaN(quantity) || quantity > leftToRefund(line)) return sum;
    return sum + toCents(line.unit_price) * quantity;
  }, 0);
}

export type RefundCheck =
  | {
      ok: true;
      lines: { sale_line_id: string; quantity: number; restock: boolean }[];
      totalCents: number;
      units: number;
    }
  | { ok: false; message: string; fields: Record<string, string> };

/** Checks the form before the confirmation dialog opens. Field keys are line ids, "reason", "note". */
export function checkRefund(
  sale: Pick<Sale, "lines">,
  draft: RefundDraft,
  reason: RefundReason | "",
  note: string,
): RefundCheck {
  const fields: Record<string, string> = {};
  const lines: { sale_line_id: string; quantity: number; restock: boolean }[] = [];

  for (const line of sale.lines) {
    const entry = draft[line.id];
    if (!entry) continue;
    const quantity = parseQuantity(entry.quantity);
    const left = leftToRefund(line);
    if (Number.isNaN(quantity)) fields[line.id] = "Enter a whole number";
    else if (quantity > left) fields[line.id] = left === 1 ? "Only 1 left to refund" : `Only ${left} left to refund`;
    else if (quantity > 0) lines.push({ sale_line_id: line.id, quantity, restock: entry.restock });
  }
  if (!reason) fields.reason = "Choose a reason";
  if (reason === "other" && !note.trim()) fields.note = "Say why, since the reason is Other";

  if (Object.keys(fields).length > 0) {
    const count = Object.keys(fields).length;
    return { ok: false, message: count === 1 ? "Fix 1 problem to continue." : `Fix ${count} problems to continue.`, fields };
  }
  if (lines.length === 0) {
    return { ok: false, message: "Enter how many to refund for at least one item.", fields: {} };
  }
  return {
    ok: true,
    lines,
    totalCents: refundTotalCents(sale, draft),
    units: lines.reduce((sum, line) => sum + line.quantity, 0),
  };
}

/** "S-000123", "s123", "123" → "123" for the API; anything else → null (shown as an error). */
export function normalizeReceiptQuery(raw: string | undefined): string | null | undefined {
  const text = raw?.trim();
  if (!text) return undefined;
  const match = /^(?:s-?)?0*(\d{1,9})$/i.exec(text);
  return match ? match[1] : null;
}

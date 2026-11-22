"use client";

import { useRef, useState, useTransition } from "react";
import { receiveAction } from "@/app/(dashboard)/purchase-orders/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { PurchaseOrder } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import type { FormState } from "@/lib/form-state";

/**
 * Record one delivery. Quantities start at what's still owed, the common case, and can be
 * lowered for a short delivery. Stock goes up and each product's cost becomes the order's cost.
 */
export function ReceiveForm({ po }: { po: PurchaseOrder }) {
  const open = po.lines.filter((line) => line.quantity_remaining > 0);
  const remaining = () => Object.fromEntries(open.map((line) => [line.id, String(line.quantity_remaining)]));
  const [quantities, setQuantities] = useState<Record<string, string>>(remaining);
  const [note, setNote] = useState("");
  const [state, setState] = useState<FormState>({ status: "idle" });
  const [isPending, startTransition] = useTransition();
  // Kept until this delivery succeeds: a retry after a network error reuses it, so stock is added once.
  const deliveryKey = useRef<string | null>(null);

  // After a delivery the page refreshes with new remaining quantities: start from those.
  // (Adjusting state while rendering, as React recommends for "reset when a prop changes".)
  const [version, setVersion] = useState(po.updated_at);
  if (version !== po.updated_at) {
    setVersion(po.updated_at);
    setQuantities(remaining());
  }

  function submit() {
    const fields: Record<string, string> = {};
    const lines = open.map((line) => {
      const raw = (quantities[line.id] ?? "").trim() || "0";
      const quantity = /^\d+$/.test(raw) ? Number(raw) : Number.NaN;
      if (Number.isNaN(quantity)) fields[line.id] = "Enter a whole number";
      else if (quantity > line.quantity_remaining) fields[line.id] = `Only ${line.quantity_remaining} left to receive`;
      return { line_id: line.id, quantity };
    });
    if (Object.keys(fields).length > 0) {
      setState({ status: "error", message: "Check the quantities.", fields });
      return;
    }
    if (lines.every((line) => line.quantity === 0)) {
      setState({ status: "error", message: "Enter how many arrived for at least one product.", fields: {} });
      return;
    }
    deliveryKey.current ??= crypto.randomUUID();
    startTransition(async () => {
      const result = await receiveAction(po.id, lines, note, deliveryKey.current!);
      setState(result);
      if (result.status === "success") deliveryKey.current = null;
    });
  }

  return (
    <form
      noValidate
      className="grid gap-4 p-4 sm:p-5"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {state.message && (
        <p
          role={state.status === "error" ? "alert" : "status"}
          className={state.status === "error" ? "text-sm font-medium text-destructive" : "text-sm font-medium text-success"}
        >
          {state.message}
        </p>
      )}
      <ul className="grid gap-3">
        {open.map((line) => {
          const error = state.fields?.[line.id];
          return (
            <li key={line.id} className="grid grid-cols-[1fr_6.5rem] items-start gap-3">
              <div className="min-w-0 pt-1.5">
                <p className="font-medium">{line.product_name}</p>
                <p className="tabular text-xs text-muted-foreground">
                  {formatNumber(line.quantity_received)} of {formatNumber(line.quantity_ordered)} {line.unit} received
                </p>
              </div>
              <label className="grid gap-1 text-xs text-muted-foreground">
                <span>Arrived ({line.unit})</span>
                <Input
                  inputMode="numeric"
                  value={quantities[line.id] ?? ""}
                  onChange={(event) => setQuantities((current) => ({ ...current, [line.id]: event.target.value }))}
                  aria-invalid={Boolean(error)}
                  aria-label={`Arrived (${line.unit}) of ${line.product_name}`}
                  className="tabular text-foreground"
                />
                {error && <span className="text-destructive">{error}</span>}
              </label>
            </li>
          );
        })}
      </ul>
      <label className="grid gap-1.5 text-sm font-medium">
        Note <span className="sr-only">(optional)</span>
        <Textarea
          rows={2}
          maxLength={280}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Delivery receipt number, damaged items…"
        />
      </label>
      <div>
        <Button type="submit" disabled={isPending}>
          {isPending ? "Recording…" : "Record delivery"}
        </Button>
      </div>
    </form>
  );
}

"use client";

import { useActionState, useLayoutEffect, useRef, useState } from "react";
import { adjustStockAction, type FormState } from "@/app/(dashboard)/products/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { MovementReason, Product } from "@/lib/api/types";
import { adjustmentReasons } from "@/lib/products";
import { cn } from "@/lib/utils";
import { FormField } from "./form-field";

const initialState: FormState = { status: "idle" };

export function StockAdjustForm({ product }: { product: Product }) {
  const [state, formAction, isPending] = useActionState(adjustStockAction.bind(null, product.id), initialState);
  const [reason, setReason] = useState<MovementReason>("purchase");
  const [chosenDirection, setChosenDirection] = useState<"add" | "remove">("add");
  // One key per submission, created at submit time (not during render, so server and client
  // HTML match). React resets the form after each action, which clears it for the next one.
  const idempotencyKeyRef = useRef<HTMLInputElement>(null);

  // When this page is hidden by <Activity> and shown again later, don't replay an old
  // "Stock updated" message: remember the state that was on screen when it was hidden.
  const [hiddenState, setHiddenState] = useState<FormState | null>(null);
  useLayoutEffect(() => () => setHiddenState(state), [state]);
  const showMessage = state !== hiddenState;

  const reasonConfig = adjustmentReasons.find((option) => option.value === reason)!;
  const direction = reasonConfig.direction === "either" ? chosenDirection : reasonConfig.direction;
  const error = (key: string) => state.fields?.[key];

  if (!product.is_active) {
    return <p className="text-muted-foreground">This product is archived, so its stock can&apos;t change.</p>;
  }

  return (
    <form
      action={formAction}
      onSubmit={() => {
        if (idempotencyKeyRef.current && !idempotencyKeyRef.current.value) {
          idempotencyKeyRef.current.value = crypto.randomUUID();
        }
      }}
      className="grid gap-4"
    >
      <input ref={idempotencyKeyRef} type="hidden" name="idempotency_key" defaultValue="" />
      <input type="hidden" name="direction" value={direction} />

      <FormField name="reason" label="Reason" error={error("reason")}>
        {({ id, describedBy }) => (
          <select
            id={id}
            name="reason"
            value={reason}
            onChange={(event) => setReason(event.target.value as MovementReason)}
            aria-describedby={describedBy}
            className="h-9 rounded-sm border border-input bg-card px-2.5 text-sm"
          >
            {adjustmentReasons.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </FormField>

      {reasonConfig.direction === "either" && (
        <fieldset className="grid gap-1.5">
          <legend className="text-sm font-medium">Change</legend>
          <div className="inline-flex w-fit rounded-sm border border-input p-0.5">
            {(["add", "remove"] as const).map((option) => (
              <label
                key={option}
                className={cn(
                  "cursor-pointer rounded-[4px] px-3 py-1.5 text-sm font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                  direction === option ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                )}
              >
                <input
                  type="radio"
                  name="direction-choice"
                  value={option}
                  checked={direction === option}
                  onChange={() => setChosenDirection(option)}
                  className="sr-only"
                />
                {option === "add" ? "Add" : "Remove"}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <FormField name="quantity"
        label={direction === "add" ? `Quantity to add (${product.unit})` : `Quantity to remove (${product.unit})`}
        required
        error={error("quantity")}
      >
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="quantity"
            type="number"
            min={1}
            step={1}
            inputMode="numeric"
            required
            defaultValue={state.status === "error" ? state.values?.quantity : ""}
            aria-invalid={Boolean(error("quantity"))}
            aria-describedby={describedBy}
            className="tabular"
          />
        )}
      </FormField>

      <FormField name="note" label="Note" hint="Optional. For example, the supplier's receipt number." error={error("note")}>
        {({ id, describedBy }) => (
          <Textarea
            id={id}
            name="note"
            rows={2}
            maxLength={280}
            defaultValue={state.status === "error" ? state.values?.note : ""}
            aria-describedby={describedBy}
          />
        )}
      </FormField>

      <div aria-live="polite" className="min-h-5 text-[0.8125rem]">
        {showMessage && state.status === "success" && <p className="font-medium text-success">{state.message}</p>}
        {showMessage && state.status === "error" && !state.fields?.quantity && (
          <p className="text-destructive">{state.message}</p>
        )}
      </div>

      <Button type="submit" disabled={isPending} className="w-full sm:w-fit">
        {isPending ? "Saving…" : direction === "add" ? "Add stock" : "Remove stock"}
      </Button>
    </form>
  );
}

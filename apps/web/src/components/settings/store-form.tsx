"use client";

import { useActionState, useEffect, useRef } from "react";
import { updateStoreAction } from "@/app/(dashboard)/settings/store/actions";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Store } from "@/lib/api/types";
import type { FormState } from "@/lib/form-state";
import type { TimeZoneOption } from "@/lib/time-zones";

interface StoreFormProps {
  store: Store;
  timeZones: TimeZoneOption[];
}

const initialState: FormState = { status: "idle" };

/** The owner's store settings form. Managers see the same values read-only (StoreDetails). */
export function StoreForm({ store, timeZones }: StoreFormProps) {
  const [state, formAction, isPending] = useActionState(updateStoreAction, initialState);
  const summaryRef = useRef<HTMLDivElement>(null);

  // After a failed save, move focus to the error summary.
  useEffect(() => {
    if (state.status === "error") summaryRef.current?.focus();
  }, [state]);

  const value = (key: "name" | "timezone" | "default_lead_time_days") =>
    state.status === "error" && state.values ? state.values[key] : String(store[key]);
  const error = (key: string) => (state.status === "error" ? state.fields?.[key] : undefined);

  return (
    <form action={formAction} noValidate className="grid gap-6">
      {state.status === "error" && (
        <div
          ref={summaryRef}
          tabIndex={-1}
          role="alert"
          className="rounded-sm border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm outline-none"
        >
          <p className="font-semibold text-destructive">{state.message}</p>
          {state.fields && Object.keys(state.fields).length > 0 && (
            <p className="mt-0.5 text-muted-foreground">Check the highlighted fields below.</p>
          )}
        </div>
      )}

      <fieldset className="grid gap-4">
        <legend className="sr-only">Store details</legend>
        <FormField name="name" label="Store name" required hint="Shown at the top of every page and on receipts." error={error("name")}>
          {({ id, describedBy }) => (
            <Input
              id={id}
              name="name"
              required
              maxLength={160}
              defaultValue={value("name")}
              aria-invalid={Boolean(error("name"))}
              aria-describedby={describedBy}
              autoComplete="organization"
            />
          )}
        </FormField>

        <FormField
          name="timezone"
          label="Time zone"
          hint="Decides where each day starts for the Overview, reports and reorder suggestions. Changing it doesn't change any records; past sales are regrouped into days in the new zone."
          error={error("timezone")}
        >
          {({ id, describedBy }) => (
            <select
              id={id}
              name="timezone"
              // A new key resets the select to the saved value after a successful save.
              key={store.timezone}
              defaultValue={value("timezone")}
              aria-invalid={Boolean(error("timezone"))}
              aria-describedby={describedBy}
              className="h-9 w-full max-w-sm rounded-sm border border-input bg-card px-2.5 text-sm"
            >
              {timeZones.map((zone) => (
                <option key={zone.value} value={zone.value}>
                  {zone.label}
                </option>
              ))}
            </select>
          )}
        </FormField>

        <FormField
          name="default_lead_time_days"
          label="Default delivery time (days)"
          hint="Used for reorder suggestions when a product's supplier has no delivery time of its own."
          error={error("default_lead_time_days")}
        >
          {({ id, describedBy }) => (
            <Input
              id={id}
              name="default_lead_time_days"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={2}
              className="max-w-28"
              defaultValue={value("default_lead_time_days")}
              aria-invalid={Boolean(error("default_lead_time_days"))}
              aria-describedby={describedBy}
            />
          )}
        </FormField>

        <div className="grid gap-1.5 text-sm">
          <span className="font-medium">Currency</span>
          <span className="tabular">{store.currency}</span>
          <span className="text-[0.8125rem] text-muted-foreground">
            Every price, cost and receipt is stored in this currency, so it can&apos;t be changed here.
          </span>
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3 border-t border-border pt-5">
        <Button type="submit" size="lg" disabled={isPending}>
          {isPending ? "Saving…" : "Save settings"}
        </Button>
        <p role="status" className="text-sm text-muted-foreground">
          {state.status === "success" && !isPending ? state.message : ""}
        </p>
      </div>
    </form>
  );
}

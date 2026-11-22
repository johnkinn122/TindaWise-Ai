"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef } from "react";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Supplier } from "@/lib/api/types";
import type { FormState } from "@/lib/form-state";

type SupplierAction = (state: FormState, formData: FormData) => Promise<FormState>;

interface SupplierFormProps {
  action: SupplierAction;
  /** Present when editing. */
  supplier?: Supplier;
  submitLabel: string;
}

const initialState: FormState = { status: "idle" };

export function SupplierForm({ action, supplier, submitLabel }: SupplierFormProps) {
  const [state, formAction, isPending] = useActionState(action, initialState);
  const summaryRef = useRef<HTMLDivElement>(null);

  // After a failed submit, move focus to the error summary.
  useEffect(() => {
    if (state.status === "error") summaryRef.current?.focus();
  }, [state]);

  const value = (key: keyof Supplier) => state.values?.[key] ?? String(supplier?.[key] ?? "");
  const error = (key: string) => state.fields?.[key];

  return (
    <form action={formAction} noValidate className="grid gap-6" ref={(form) => () => form?.reset()}>
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
        <legend className="sr-only">Supplier details</legend>
        <FormField name="name" label="Supplier name" required error={error("name")}>
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
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField name="contact_name" label="Contact person" error={error("contact_name")}>
            {({ id, describedBy }) => (
              <Input
                id={id}
                name="contact_name"
                maxLength={120}
                defaultValue={value("contact_name")}
                aria-invalid={Boolean(error("contact_name"))}
                aria-describedby={describedBy}
                autoComplete="name"
              />
            )}
          </FormField>
          <FormField name="phone" label="Phone" error={error("phone")}>
            {({ id, describedBy }) => (
              <Input
                id={id}
                name="phone"
                type="tel"
                maxLength={40}
                defaultValue={value("phone")}
                aria-invalid={Boolean(error("phone"))}
                aria-describedby={describedBy}
                autoComplete="tel"
              />
            )}
          </FormField>
        </div>
        <FormField name="email" label="Email" error={error("email")}>
          {({ id, describedBy }) => (
            <Input
              id={id}
              name="email"
              type="email"
              maxLength={254}
              defaultValue={value("email")}
              aria-invalid={Boolean(error("email"))}
              aria-describedby={describedBy}
              autoComplete="email"
            />
          )}
        </FormField>
        <FormField name="notes" label="Notes" hint="Delivery days, payment terms, minimum order." error={error("notes")}>
          {({ id, describedBy }) => (
            <Textarea
              id={id}
              name="notes"
              maxLength={500}
              rows={3}
              defaultValue={value("notes")}
              aria-invalid={Boolean(error("notes"))}
              aria-describedby={describedBy}
            />
          )}
        </FormField>
      </fieldset>

      <div className="flex flex-wrap gap-2 border-t border-border pt-5">
        <Button type="submit" size="lg" disabled={isPending}>
          {isPending ? "Saving…" : submitLabel}
        </Button>
        <Button variant="ghost" size="lg" asChild>
          <Link href="/suppliers">Cancel</Link>
        </Button>
      </div>
    </form>
  );
}

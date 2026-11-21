"use client";

import { useActionState } from "react";
import { addMemberAction, type MemberFormState } from "@/app/(dashboard)/settings/team/actions";
import { FormError } from "@/components/auth/form-error";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const initialState: MemberFormState = { status: "idle" };

export function AddMemberForm() {
  const [state, formAction, isPending] = useActionState(addMemberAction, initialState);
  const error = (key: string) => (state.status === "error" ? state.fields?.[key] : undefined);
  const value = (key: string) => (state.status === "error" ? state.values?.[key] : undefined);

  return (
    <form action={formAction} className="grid gap-4" ref={(form) => () => form?.reset()}>
      <FormError message={state.status === "error" ? state.message : undefined} version={state} />
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField name="full_name" label="Name" required error={error("full_name")}>
          {({ id, describedBy }) => (
            <Input
              id={id}
              name="full_name"
              required
              maxLength={120}
              autoComplete="off"
              defaultValue={value("full_name")}
              aria-invalid={Boolean(error("full_name"))}
              aria-describedby={describedBy}
            />
          )}
        </FormField>
        <FormField name="email" label="Email" required error={error("email")}>
          {({ id, describedBy }) => (
            <Input
              id={id}
              name="email"
              type="email"
              required
              autoComplete="off"
              defaultValue={value("email")}
              aria-invalid={Boolean(error("email"))}
              aria-describedby={describedBy}
            />
          )}
        </FormField>
        <FormField
          name="role"
          label="Role"
          hint="Managers run products and stock. Cashiers look things up and will sell."
          error={error("role")}
        >
          {({ id, describedBy }) => (
            <select
              id={id}
              name="role"
              defaultValue={value("role") ?? "cashier"}
              aria-describedby={describedBy}
              className="h-9 rounded-sm border border-input bg-card px-2.5 text-sm"
            >
              <option value="cashier">Cashier</option>
              <option value="manager">Manager</option>
            </select>
          )}
        </FormField>
        <FormField
          name="temporary_password"
          label="Temporary password"
          required
          hint="At least 10 characters. Share it with them in person."
          error={error("temporary_password")}
        >
          {({ id, describedBy }) => (
            <Input
              id={id}
              name="temporary_password"
              type="password"
              required
              minLength={10}
              maxLength={128}
              autoComplete="new-password"
              aria-invalid={Boolean(error("temporary_password"))}
              aria-describedby={describedBy}
            />
          )}
        </FormField>
      </div>
      <div aria-live="polite" className="min-h-5 text-sm">
        {state.status === "success" && <p className="font-medium text-success">{state.message}</p>}
      </div>
      <Button type="submit" disabled={isPending} className="w-full sm:w-fit">
        {isPending ? "Adding…" : "Add team member"}
      </Button>
    </form>
  );
}

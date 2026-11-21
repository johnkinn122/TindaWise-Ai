"use client";

import Link from "next/link";
import { useActionState } from "react";
import { type AuthFormState, signupAction } from "@/app/(auth)/actions";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormError } from "./form-error";

const initialState: AuthFormState = { status: "idle" };

export function SignupForm() {
  const [state, formAction, isPending] = useActionState(signupAction, initialState);
  const error = (key: string) => state.fields?.[key];

  return (
    <form action={formAction} className="grid gap-4">
      <FormError message={state.message} version={state} />

      <FormField name="full_name" label="Your name" required error={error("full_name")}>
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="full_name"
            autoComplete="name"
            required
            maxLength={120}
            defaultValue={state.values?.full_name}
            aria-invalid={Boolean(error("full_name"))}
            aria-describedby={describedBy}
            className="h-11"
          />
        )}
      </FormField>
      <FormField name="store_name" label="Store name" required hint="You can change it later." error={error("store_name")}>
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="store_name"
            autoComplete="organization"
            required
            maxLength={160}
            defaultValue={state.values?.store_name}
            aria-invalid={Boolean(error("store_name"))}
            aria-describedby={describedBy}
            className="h-11"
          />
        )}
      </FormField>
      <FormField name="email" label="Email" required error={error("email")}>
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="email"
            type="email"
            autoComplete="email"
            required
            defaultValue={state.values?.email}
            aria-invalid={Boolean(error("email"))}
            aria-describedby={describedBy}
            className="h-11"
          />
        )}
      </FormField>
      <FormField name="password" label="Password" required hint="At least 10 characters." error={error("password")}>
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={128}
            aria-invalid={Boolean(error("password"))}
            aria-describedby={describedBy}
            className="h-11"
          />
        )}
      </FormField>

      <Button type="submit" size="lg" disabled={isPending} className="mt-1 w-full">
        {isPending ? "Creating your store…" : "Create account"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </form>
  );
}

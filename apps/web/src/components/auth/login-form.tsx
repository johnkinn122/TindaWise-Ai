"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useActionState } from "react";
import { type AuthFormState, loginAction } from "@/app/(auth)/actions";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormError } from "./form-error";

const initialState: AuthFormState = { status: "idle" };

export function LoginForm() {
  const [state, formAction, isPending] = useActionState(loginAction, initialState);
  const searchParams = useSearchParams();
  const sessionEnded = searchParams.get("reason") === "session" && state.status === "idle";

  return (
    <form action={formAction} className="grid gap-4">
      <input type="hidden" name="next" value={searchParams.get("next") ?? "/"} />
      {sessionEnded && (
        <p role="status" className="rounded-sm bg-muted px-4 py-3 text-sm">
          Your session ended. Sign in again to continue.
        </p>
      )}
      <FormError message={state.message} version={state} />

      <FormField name="email" label="Email" error={state.fields?.email}>
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="email"
            type="email"
            autoComplete="email"
            required
            defaultValue={state.values?.email}
            aria-invalid={Boolean(state.fields?.email)}
            aria-describedby={describedBy}
            className="h-11"
          />
        )}
      </FormField>
      <FormField name="password" label="Password" error={state.fields?.password}>
        {({ id, describedBy }) => (
          <Input
            id={id}
            name="password"
            type="password"
            autoComplete="current-password"
            required
            aria-invalid={Boolean(state.fields?.password)}
            aria-describedby={describedBy}
            className="h-11"
          />
        )}
      </FormField>

      <Button type="submit" size="lg" disabled={isPending} className="mt-1 w-full">
        {isPending ? "Signing in…" : "Sign in"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        New to Tindawise?{" "}
        <Link href="/signup" className="font-medium text-foreground underline underline-offset-4">
          Create an account
        </Link>
      </p>
    </form>
  );
}

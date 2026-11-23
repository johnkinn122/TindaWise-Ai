"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useActionState, useEffect, useRef } from "react";
import { type AuthFormState, loginAction, wakeApiAction } from "@/app/(auth)/actions";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormError } from "./form-error";

const initialState: AuthFormState = { status: "idle" };

interface LoginFormProps {
  /** The public demo: its accounts (one click fills the form) and their shared password. */
  demo?: { accounts: { email: string; label: string }[]; password: string };
}

export function LoginForm({ demo }: LoginFormProps) {
  const [state, formAction, isPending] = useActionState(loginAction, initialState);
  const searchParams = useSearchParams();
  const sessionEnded = searchParams.get("reason") === "session" && state.status === "idle";
  const formRef = useRef<HTMLFormElement>(null);

  // The demo API sleeps when idle: start waking it while the visitor reads and types.
  useEffect(() => {
    if (demo) void wakeApiAction();
  }, [demo]);

  function fill(email: string) {
    const form = formRef.current;
    if (!form || !demo) return;
    (form.elements.namedItem("email") as HTMLInputElement).value = email;
    (form.elements.namedItem("password") as HTMLInputElement).value = demo.password;
    form.querySelector<HTMLButtonElement>("button[type=submit]")?.focus();
  }

  return (
    <form ref={formRef} action={formAction} className="grid gap-4">
      {demo && (
        <section aria-labelledby="demo-accounts" className="rounded-sm border border-border bg-muted/50 p-3 text-sm">
          <h2 id="demo-accounts" className="font-semibold">
            Demo accounts
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Password for all: <code className="font-medium text-foreground">{demo.password}</code>
          </p>
          <ul className="mt-2 grid gap-1.5">
            {demo.accounts.map((account) => (
              <li key={account.email} className="flex items-center justify-between gap-3">
                <span className="min-w-0">
                  <span className="block break-all">{account.email}</span>
                  <span className="block text-xs text-muted-foreground">{account.label}</span>
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                  onClick={() => fill(account.email)}
                  aria-label={`Use ${account.email}`}
                >
                  Use
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
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
      {demo ? (
        <p className="text-center text-xs text-muted-foreground">
          The demo server sleeps when nobody is using it, so the first sign-in can take up to a minute.
        </p>
      ) : (
        <p className="text-center text-sm text-muted-foreground">
          New to Tindawise?{" "}
          <Link href="/signup" className="font-medium text-foreground underline underline-offset-4">
            Create an account
          </Link>
        </p>
      )}
    </form>
  );
}

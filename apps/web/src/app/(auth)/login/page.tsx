import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "@/components/auth/login-form";
import { Skeleton } from "@/components/ui/skeleton";
import { DEMO_ACCOUNTS, DEMO_PASSWORD, isDemo } from "@/lib/demo";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return (
    <>
      <h1 className="font-display text-2xl font-bold">Sign in</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">Welcome back. Check today&apos;s sales and stock.</p>
      {/* The form reads ?next= and ?reason= from the URL, which is request-time data. */}
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <LoginForm demo={isDemo() ? { accounts: DEMO_ACCOUNTS, password: DEMO_PASSWORD } : undefined} />
      </Suspense>
    </>
  );
}

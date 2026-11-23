import type { Metadata } from "next";
import Link from "next/link";
import { SignupForm } from "@/components/auth/signup-form";
import { Button } from "@/components/ui/button";
import { isDemo } from "@/lib/demo";

export const metadata: Metadata = {
  title: "Create account",
};

export default function SignupPage() {
  if (isDemo()) {
    return (
      <>
        <h1 className="font-display text-2xl font-bold">Sign-up is off on the demo</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">
          This is a public demo with sample data, so it doesn&apos;t take new accounts. Sign in with one of the demo
          accounts instead.
        </p>
        <Button asChild size="lg" className="w-full">
          <Link href="/login">Go to sign in</Link>
        </Button>
      </>
    );
  }
  return (
    <>
      <h1 className="font-display text-2xl font-bold">Create your store</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        You&apos;ll be the owner. Add your staff after you sign in.
      </p>
      <SignupForm />
    </>
  );
}

import type { Metadata } from "next";
import { SignupForm } from "@/components/auth/signup-form";

export const metadata: Metadata = {
  title: "Create account",
};

export default function SignupPage() {
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

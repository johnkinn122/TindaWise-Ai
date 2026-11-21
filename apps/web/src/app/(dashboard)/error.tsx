"use client";

import { Button } from "@/components/ui/button";

/** Last-resort error screen for anything inside the app shell that wasn't handled locally. */
export default function DashboardError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="grid place-items-center rounded-lg border border-border bg-card px-6 py-16 text-center">
      <h1 className="font-display text-xl font-semibold">This page didn&apos;t load</h1>
      <p className="mt-1.5 max-w-md text-muted-foreground">
        Something went wrong while loading it. Try again; if it keeps happening, check that the API is running.
      </p>
      <Button variant="outline" className="mt-5" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}

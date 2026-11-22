import { CloudOff } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

/** Shown when the API can't be reached. States the cause and the way out (MASTER.md §10). */
export function ApiErrorState({ retryHref, title = "Can't load products" }: { retryHref: string; title?: string }) {
  return (
    <div role="alert" className="grid place-items-center px-6 py-14 text-center">
      <CloudOff className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
      <h2 className="mt-4 font-display text-xl font-semibold">{title}</h2>
      <p className="mt-1.5 max-w-md text-muted-foreground">
        The Tindawise API isn&apos;t responding. Start it with{" "}
        <code className="rounded-sm bg-muted px-1 py-0.5 text-[0.8125rem]">npm run dev:api</code>, then try again.
      </p>
      <Button variant="outline" className="mt-5" asChild>
        <Link href={retryHref}>Try again</Link>
      </Button>
    </div>
  );
}

"use client";

import { useRef, useState, useTransition } from "react";
import { createFromReorderAction } from "@/app/(dashboard)/purchase-orders/actions";
import { Button } from "@/components/ui/button";

/**
 * Drafts a purchase order from the reorder suggestions and opens it for review. Nothing is
 * ordered here: the draft still needs a supplier and the owner's approval.
 */
export function CreateOrderFromSuggestionsButton() {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string>();
  // Kept across retries, so a double click or a retried request creates one draft.
  const key = useRef<string | null>(null);

  function create() {
    setError(undefined);
    key.current ??= crypto.randomUUID();
    startTransition(async () => {
      const result = await createFromReorderAction(key.current!);
      if (result?.status === "error") setError(result.message);
    });
  }

  return (
    <div className="grid gap-1.5">
      <div>
        <Button onClick={create} disabled={isPending} aria-describedby="reorder-draft-note">
          {isPending ? "Creating draft…" : "Create purchase order"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

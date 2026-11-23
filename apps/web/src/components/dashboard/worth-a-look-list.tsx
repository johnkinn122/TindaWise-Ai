"use client";

import { ArrowDown, ArrowUp, PackageMinus } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState, useTransition } from "react";
import { dismissAnomalyAction } from "@/app/(dashboard)/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  anomalyKey,
  anomalySummary,
  salesItem,
  stockItem,
  stockLossSummary,
  type WorthALookItem,
} from "@/lib/anomalies";
import type { AnomalyAlert, StockLossAlert } from "@/lib/api/types";

const NOTE_MAX = 280;

const ICONS = {
  spike: { Icon: ArrowUp, className: "text-info" },
  drop: { Icon: ArrowDown, className: "text-warning" },
  shrinkage: { Icon: PackageMinus, className: "text-warning" },
} as const;

/**
 * Two groups: unusual sales days and stock going missing. Each row has a Dismiss action.
 * Dismissing refreshes the page from the server, so the row disappears; a live region says so,
 * and focus moves to the group's summary, since the focused button goes with the row.
 */
export function WorthALookList({ alerts, losses }: { alerts: AnomalyAlert[]; losses: StockLossAlert[] }) {
  const [announcement, setAnnouncement] = useState("");

  return (
    <>
      <p role="status" className="sr-only">
        {announcement}
      </p>
      <Group
        heading="Unusual sales days"
        summary={alerts.length === 0 ? "Nothing unusual in the last 7 days." : anomalySummary(alerts.length)}
        items={alerts.map(salesItem)}
        onDismissed={(name) => setAnnouncement(`Alert for ${name} dismissed.`)}
      />
      <Group
        heading="Stock going missing"
        summary={
          losses.length === 0
            ? "No stock count in the last 8 weeks found 5% or more of sales missing."
            : stockLossSummary(losses.length)
        }
        items={losses.map(stockItem)}
        onDismissed={(name) => setAnnouncement(`Alert for ${name} dismissed.`)}
      />
    </>
  );
}

function Group({
  heading,
  summary,
  items,
  onDismissed,
}: {
  heading: string;
  summary: string;
  items: WorthALookItem[];
  onDismissed: (name: string) => void;
}) {
  const headingId = useId();
  const summaryRef = useRef<HTMLParagraphElement>(null);

  function dismissed(name: string) {
    onDismissed(name);
    summaryRef.current?.focus();
  }

  return (
    <section aria-labelledby={headingId} className="border-b border-border pb-3 pt-3.5 last-of-type:border-b-0">
      <h3 id={headingId} className="px-4 text-sm font-semibold sm:px-5">
        {heading}
      </h3>
      <p
        ref={summaryRef}
        tabIndex={-1}
        className="mt-0.5 px-4 text-[0.8125rem] text-muted-foreground outline-none sm:px-5"
      >
        {summary}
      </p>
      {items.length > 0 && (
        <ul className="mt-2 divide-y divide-border border-t border-border text-[0.8125rem]">
          {items.map((item) => (
            <AlertRow key={anomalyKey(item)} item={item} onDismissed={dismissed} />
          ))}
        </ul>
      )}
    </section>
  );
}

function AlertRow({ item, onDismissed }: { item: WorthALookItem; onDismissed: (name: string) => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string>();
  const [isPending, startTransition] = useTransition();
  const noteRef = useRef<HTMLInputElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const noteId = useId();
  const hintId = useId();
  const errorId = useId();
  const { Icon, className: iconColor } = ICONS[item.kind];

  // Move focus into the form when it opens, and back to "Dismiss" when it's cancelled.
  useEffect(() => {
    if (open) noteRef.current?.focus();
    else if (wasOpen.current) openRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    startTransition(async () => {
      const result = await dismissAnomalyAction({
        product_id: item.product_id,
        day: item.day,
        kind: item.kind,
        note,
      });
      if (result.status === "error") setError(result.fields?.note ?? result.message);
      else onDismissed(item.name);
    });
  }

  return (
    <li className="px-4 py-3 sm:px-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* The product page shows the stock history behind the alert. */}
          <Link
            href={`/products/${item.product_id}`}
            className="font-medium underline-offset-4 hover:underline focus-visible:underline"
          >
            {item.name}
          </Link>
          {/* No separator dot: when the date wraps in a narrow column, a dot would start the line. */}
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2.5 text-xs">
            <span className="inline-flex items-center gap-1 font-medium">
              <Icon className={`size-3.5 ${iconColor}`} strokeWidth={2} aria-hidden="true" />
              {item.title}
            </span>
            <time dateTime={item.day} className="text-muted-foreground">
              {item.when}
            </time>
          </p>
          <p className="tabular mt-0.5 text-xs text-muted-foreground">{item.detail}</p>
        </div>
        {!open && (
          <Button
            ref={openRef}
            variant="outline"
            className="shrink-0"
            onClick={() => setOpen(true)}
            aria-label={`Dismiss alert for ${item.name}, ${item.when}`}
          >
            Dismiss
          </Button>
        )}
      </div>

      {open && (
        <form onSubmit={submit} className="mt-3 grid gap-2">
          <div className="grid gap-1.5">
            <Label htmlFor={noteId}>Note (optional)</Label>
            <Input
              ref={noteRef}
              id={noteId}
              value={note}
              maxLength={NOTE_MAX}
              onChange={(event) => setNote(event.target.value)}
              aria-describedby={error ? `${hintId} ${errorId}` : hintId}
              aria-invalid={error ? true : undefined}
              placeholder={item.kind === "shrinkage" ? "e.g. Recounted, the shelf was right" : "e.g. Store closed for the fiesta"}
            />
            <p id={hintId} className="text-xs text-muted-foreground">
              Saved with your name in the activity log.
            </p>
            {error && (
              <p id={errorId} role="alert" className="text-xs text-destructive">
                {error}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={isPending}>
              {isPending ? "Dismissing…" : "Dismiss alert"}
            </Button>
            <Button type="button" variant="ghost" disabled={isPending} onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </li>
  );
}

"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useEffect, useId, useRef, useState, useTransition } from "react";
import { dismissAnomalyAction } from "@/app/(dashboard)/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { anomalyDetail, anomalyKey, anomalySummary, anomalyTitle } from "@/lib/anomalies";
import type { AnomalyAlert } from "@/lib/api/types";
import { formatCalendarDay } from "@/lib/format";

const NOTE_MAX = 280;

/**
 * The alerts, each with a Dismiss action. Dismissing refreshes the page from the server, so the
 * row disappears; a live region says so, since the focused button goes with it.
 */
export function WorthALookList({ alerts }: { alerts: AnomalyAlert[] }) {
  const [announcement, setAnnouncement] = useState("");
  const summaryRef = useRef<HTMLParagraphElement>(null);

  function dismissed(name: string) {
    setAnnouncement(`Alert for ${name} dismissed.`);
    summaryRef.current?.focus();
  }

  return (
    <>
      <p role="status" className="sr-only">
        {announcement}
      </p>
      {alerts.length === 0 ? (
        <p ref={summaryRef} tabIndex={-1} className="px-4 pt-5 text-[0.8125rem] text-muted-foreground outline-none sm:px-5">
          Nothing unusual in the last 7 days.
        </p>
      ) : (
        <>
          <p
            ref={summaryRef}
            tabIndex={-1}
            className="px-4 pt-3.5 text-[0.8125rem] text-muted-foreground outline-none sm:px-5"
          >
            {anomalySummary(alerts.length)}
          </p>
          <ul className="mt-2 divide-y divide-border border-y border-border text-[0.8125rem]">
            {alerts.map((alert) => (
              <AlertRow key={anomalyKey(alert)} alert={alert} onDismissed={dismissed} />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function AlertRow({ alert, onDismissed }: { alert: AnomalyAlert; onDismissed: (name: string) => void }) {
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
  const Icon = alert.kind === "spike" ? ArrowUp : ArrowDown;

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
        product_id: alert.product_id,
        day: alert.day,
        kind: alert.kind,
        note,
      });
      if (result.status === "error") setError(result.fields?.note ?? result.message);
      else onDismissed(alert.name);
    });
  }

  return (
    <li className="px-4 py-3 sm:px-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium">{alert.name}</p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs">
            <span className="inline-flex items-center gap-1 font-medium">
              <Icon
                className={alert.kind === "spike" ? "size-3.5 text-info" : "size-3.5 text-warning"}
                strokeWidth={2}
                aria-hidden="true"
              />
              {anomalyTitle(alert)}
            </span>
            <span className="text-muted-foreground">
              <span aria-hidden="true">· </span>
              <time dateTime={alert.day}>{formatCalendarDay(alert.day)}</time>
            </span>
          </p>
          <p className="tabular mt-0.5 text-xs text-muted-foreground">{anomalyDetail(alert)}</p>
        </div>
        {!open && (
          <Button
            ref={openRef}
            variant="outline"
            className="shrink-0"
            onClick={() => setOpen(true)}
            aria-label={`Dismiss alert for ${alert.name}, ${formatCalendarDay(alert.day)}`}
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
              placeholder="e.g. Store closed for the fiesta"
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

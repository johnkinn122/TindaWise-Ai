"use client";

import Link from "next/link";
import { useId, useRef, useState, useTransition } from "react";
import { refundAction } from "@/app/(dashboard)/sales/actions";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { RefundReason, Sale } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";
import {
  checkRefund,
  emptyDraft,
  fullDraft,
  leftToRefund,
  payBackWording,
  type RefundDraft,
  refundReasons,
  refundTotalCents,
} from "@/lib/sales";
import { cn } from "@/lib/utils";

interface Problems {
  message: string;
  fields: Record<string, string>;
}

/**
 * Refund some or all of a receipt. Quantities start at 0 so nothing is refunded by accident;
 * "Refund everything" fills in what's left. Giving money back can't be undone, so the last step
 * is a confirmation that names the amount and how it's paid back (MASTER.md §5).
 */
export function RefundForm({ sale }: { sale: Sale }) {
  const uid = useId(); // unique ids even if a hidden copy of this page stays in the DOM
  const fieldId = (key: string) => `${uid}-${key}`;
  const lines = sale.lines.filter((line) => leftToRefund(line) > 0);

  const [draft, setDraft] = useState<RefundDraft>(() => emptyDraft(sale));
  const [reason, setReason] = useState<RefundReason | "">("");
  const [note, setNote] = useState("");
  const [problems, setProblems] = useState<Problems | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [isPending, startTransition] = useTransition();
  const summaryRef = useRef<HTMLDivElement>(null);
  // Kept until this refund succeeds: a retry after a network error reuses it, so money goes back once.
  const refundKey = useRef<string | null>(null);

  const totalCents = refundTotalCents(sale, draft);
  const check = checkRefund(sale, draft, reason, note);

  function showProblems(next: Problems) {
    setProblems(next);
    // After the error list renders, move focus to it so keyboard and screen reader users land there.
    requestAnimationFrame(() => summaryRef.current?.focus());
  }

  function review() {
    if (!check.ok) {
      showProblems({ message: check.message, fields: check.fields });
      return;
    }
    setProblems(null);
    setConfirming(true);
  }

  function confirm() {
    if (!check.ok || !reason) return;
    refundKey.current ??= crypto.randomUUID();
    startTransition(async () => {
      // On success the action redirects to the receipt; only refusals come back here.
      const result = await refundAction(sale.id, { lines: check.lines, reason, note }, refundKey.current!);
      setConfirming(false);
      if (result.status === "error") {
        showProblems({ message: result.message ?? "The refund wasn't recorded.", fields: result.fields ?? {} });
      }
    });
  }

  const setLine = (id: string, change: Partial<RefundDraft[string]>) =>
    setDraft((current) => ({ ...current, [id]: { ...current[id], ...change } }));
  const fieldError = (key: string) => problems?.fields[key];
  const lineName = (id: string) => sale.lines.find((line) => line.id === id)?.product_name;
  const notRestocked = check.ok ? check.lines.filter((line) => !line.restock).reduce((n, line) => n + line.quantity, 0) : 0;

  return (
    <form
      noValidate
      className="grid gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        review();
      }}
    >
      {problems && (
        <div
          ref={summaryRef}
          tabIndex={-1}
          role="alert"
          aria-labelledby={fieldId("problems")}
          className="rounded-sm border border-destructive/50 bg-destructive/5 px-3 py-2.5 text-sm focus-visible:outline-2 focus-visible:outline-ring"
        >
          <p id={fieldId("problems")} className="font-medium text-destructive">
            {problems.message}
          </p>
          {Object.keys(problems.fields).length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {Object.entries(problems.fields).map(([key, message]) => (
                <li key={key}>
                  <a href={`#${fieldId(key)}`} className="underline underline-offset-2">
                    {lineName(key) ? `${lineName(key)}: ${message}` : message}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <section aria-labelledby={fieldId("items-title")} className="rounded-lg border border-border bg-card">
        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-2.5 sm:px-5">
          <h2 id={fieldId("items-title")} className="text-lg font-semibold leading-snug">
            Items to refund
          </h2>
          <Button type="button" variant="outline" onClick={() => setDraft((current) => fullDraft(sale, current))}>
            Refund everything
          </Button>
        </div>
        <ul className="divide-y divide-border">
          {lines.map((line) => {
            const left = leftToRefund(line);
            const error = fieldError(line.id);
            const entry = draft[line.id];
            return (
              <li key={line.id} className="grid gap-3 px-4 py-3.5 sm:grid-cols-[1fr_7rem_10rem] sm:items-start sm:px-5">
                <div className="min-w-0 sm:pt-6">
                  <p className="font-medium">{line.product_name}</p>
                  <p className="tabular text-xs text-muted-foreground">
                    {formatCents(toCents(line.unit_price))} each · {formatNumber(left)} of {formatNumber(line.quantity)} {line.unit}{" "}
                    left to refund
                  </p>
                </div>
                <div className="grid gap-1">
                  <label htmlFor={fieldId(line.id)} className="text-xs text-muted-foreground">
                    Refund ({line.unit})
                  </label>
                  <Input
                    id={fieldId(line.id)}
                    inputMode="numeric"
                    autoComplete="off"
                    value={entry.quantity}
                    onFocus={(event) => event.target.select()}
                    onChange={(event) => setLine(line.id, { quantity: event.target.value })}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? fieldId(`${line.id}-error`) : undefined}
                    aria-label={`Refund (${line.unit}) of ${line.product_name}, up to ${left}`}
                    className="tabular h-11 sm:h-9"
                  />
                  {error && (
                    <span id={fieldId(`${line.id}-error`)} className="text-xs text-destructive">
                      {error}
                    </span>
                  )}
                </div>
                <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm sm:mt-5 sm:min-h-9">
                  <input
                    type="checkbox"
                    checked={entry.restock}
                    onChange={(event) => setLine(line.id, { restock: event.target.checked })}
                    className="size-4 accent-[var(--primary)]"
                    aria-describedby={fieldId("restock-hint")}
                  />
                  <span>
                    Back on shelf
                    <span className="sr-only"> ({line.product_name})</span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        <p id={fieldId("restock-hint")} className="border-t border-border px-4 py-3 text-xs text-muted-foreground sm:px-5">
          &ldquo;Back on shelf&rdquo; adds the units to stock again. Untick it for damaged or spoiled items: stock stays as it
          is and their cost counts as a loss.
        </p>
      </section>

      <fieldset
        className="grid gap-2"
        aria-describedby={fieldError("reason") ? fieldId("reason-error") : undefined}
        aria-invalid={Boolean(fieldError("reason"))}
      >
        <legend className="mb-1 text-sm font-medium">Reason</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {refundReasons.map((option, index) => (
            <label
              key={option.id}
              className={cn(
                "flex cursor-pointer items-start gap-2.5 rounded-sm border border-input bg-card px-3 py-2.5 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary/5 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                fieldError("reason") && "border-destructive/60",
              )}
            >
              <input
                id={index === 0 ? fieldId("reason") : undefined}
                type="radio"
                name={fieldId("reason-choice")}
                value={option.id}
                checked={reason === option.id}
                onChange={() => setReason(option.id)}
                className="mt-0.5 size-4 accent-[var(--primary)]"
              />
              <span>
                <span className="block font-medium">{option.label}</span>
                <span className="block text-xs text-muted-foreground">{option.hint}</span>
              </span>
            </label>
          ))}
        </div>
        {fieldError("reason") && (
          <p id={fieldId("reason-error")} className="text-xs text-destructive">
            {fieldError("reason")}
          </p>
        )}
      </fieldset>

      <div className="grid gap-1.5">
        <label htmlFor={fieldId("note")} className="text-sm font-medium">
          Note{" "}
          <span className="font-normal text-muted-foreground">{reason === "other" ? "(required)" : "(optional)"}</span>
        </label>
        <Textarea
          id={fieldId("note")}
          rows={2}
          maxLength={280}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          aria-invalid={Boolean(fieldError("note"))}
          aria-describedby={fieldError("note") ? fieldId("note-error") : undefined}
          placeholder="What happened, anything the next person should know"
        />
        {fieldError("note") && (
          <p id={fieldId("note-error")} className="text-xs text-destructive">
            {fieldError("note")}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card px-4 py-3.5 sm:px-5">
        <p className="text-sm" aria-live="polite">
          <span className="text-muted-foreground">Refund total</span>{" "}
          <span className="tabular font-display text-xl font-semibold">{formatCents(totalCents)}</span>{" "}
          <span className="text-muted-foreground">paid back {payBackWording[sale.payment_method]}</span>
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" asChild>
            <Link href={`/sales/${sale.id}`}>Cancel</Link>
          </Button>
          <Button type="submit" size="lg" disabled={isPending}>
            Review refund
          </Button>
        </div>
      </div>

      <AlertDialog open={confirming} onOpenChange={(open) => !isPending && setConfirming(open)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Refund {formatCents(totalCents)}?</AlertDialogTitle>
            <AlertDialogDescription>
              {check.ok && (
                <>
                  Give {formatCents(check.totalCents)} back {payBackWording[sale.payment_method]} for{" "}
                  {check.units === 1 ? "1 item" : `${formatNumber(check.units)} items`} on receipt {sale.receipt_code}.{" "}
                  {notRestocked === 0
                    ? "Everything goes back in stock."
                    : notRestocked === check.units
                      ? "Nothing goes back in stock."
                      : `${formatNumber(check.units - notRestocked)} go back in stock; ${formatNumber(notRestocked)} don't.`}{" "}
                  A refund can&apos;t be undone.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isPending}>Go back</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                confirm();
              }}
              disabled={isPending}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {isPending ? "Recording…" : `Refund ${formatCents(totalCents)}`}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  );
}

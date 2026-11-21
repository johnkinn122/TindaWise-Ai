import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatNumber, formatPeso } from "@/lib/format";
import type { ReorderSuggestion } from "@/lib/sample-data";

/**
 * The Resibo card — Tindawise's signature element (MASTER.md §7).
 * Reserved for AI output only, so its receipt look always means "this came from the AI".
 *
 * The actions are intentionally inert for now: claude.md requires human approval before
 * any purchase order is created, and that approval flow belongs to the backend phase.
 */
export function ResiboCard({ suggestion }: { suggestion: ReorderSuggestion }) {
  const total = suggestion.lines.reduce((sum, line) => sum + line.quantity * line.unitCost, 0);
  const titleId = `resibo-${suggestion.id}`;

  return (
    <section aria-labelledby={titleId} className="resibo">
      <span className="inline-flex items-center gap-1.5 rounded-b-sm bg-accent px-2.5 py-1 text-xs font-semibold text-accent-foreground">
        <Sparkles className="size-3" strokeWidth={2.5} aria-hidden="true" />
        Reorder suggestion
      </span>

      <h2 id={titleId} className="mt-3.5 font-display text-lg font-semibold leading-snug">
        {suggestion.title}
      </h2>
      <p className="mt-1 text-[0.8125rem] text-muted-foreground">{suggestion.reason}</p>

      <ul className="mt-3.5 grid gap-2 border-y border-dashed border-border py-3 text-[0.8125rem]">
        {suggestion.lines.map((line) => (
          <li key={line.productId} className="resibo-line">
            <span>{line.name}</span>
            <b className="tabular font-semibold">
              {formatNumber(line.quantity)} {line.unit}
            </b>
          </li>
        ))}
      </ul>

      <div className="tabular flex justify-between py-3 font-semibold">
        <span>Estimated cost</span>
        <span>{formatPeso(total)}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button disabled aria-describedby={`${titleId}-pending`}>
          Create purchase order
        </Button>
        <Button variant="ghost" disabled aria-describedby={`${titleId}-pending`}>
          Dismiss
        </Button>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        {suggestion.basis}. Supplier: {suggestion.supplier}
      </p>
      <p id={`${titleId}-pending`} className="mt-1 text-xs text-muted-foreground">
        Actions turn on when purchase orders are built.
      </p>
    </section>
  );
}

import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { Overview } from "@/lib/api/types";
import { formatNumber, formatPeso } from "@/lib/format";
import { toCents } from "@/lib/money";
import { Panel } from "./panel";

interface ReorderCardProps {
  reorder: Overview["reorder"];
  /** Owners and managers; cashiers see the list without the ordering action. */
  canOrder: boolean;
}

/**
 * Rule-based reorder suggestions from reorder levels and recent sales.
 * Deliberately a plain Panel, not the Resibo card: that receipt look is reserved for AI output
 * (MASTER.md §7), and this is a fixed rule, not a model. The forecast-based Resibo card returns
 * in the ML phase.
 */
export function ReorderCard({ reorder, canOrder }: ReorderCardProps) {
  const { lines, total_count: totalCount, lookback_days: days, estimated_cost: estimatedCost } = reorder;
  const hidden = totalCount - lines.length;

  return (
    <Panel title="Reorder suggestions">
      {lines.length === 0 ? (
        <p className="px-4 py-5 text-[0.8125rem] text-muted-foreground sm:px-5">
          Nothing to reorder. Every product is above its reorder level.
        </p>
      ) : (
        <>
          <p className="px-4 pt-3.5 text-[0.8125rem] text-muted-foreground sm:px-5">
            {totalCount === 1 ? "1 item is" : `${formatNumber(totalCount)} items are`} at or below the reorder level.
          </p>
          <ul className="mt-2 divide-y divide-border border-y border-border text-[0.8125rem]">
            {lines.map((line) => (
              <li key={line.product_id} className="flex items-start justify-between gap-3 px-4 py-2.5 sm:px-5">
                <div className="min-w-0">
                  <p className="font-medium">{line.name}</p>
                  <p className="tabular text-xs text-muted-foreground">
                    {formatNumber(line.stock_on_hand)} on hand · {formatNumber(line.sold_recently)} sold in {days} days
                  </p>
                </div>
                <b className="tabular shrink-0 font-semibold">
                  {formatNumber(line.suggested_quantity)} {line.unit}
                </b>
              </li>
            ))}
          </ul>
          {hidden > 0 && (
            <p className="px-4 pt-2.5 text-xs text-muted-foreground sm:px-5">
              {formatNumber(hidden)} more not shown.{" "}
              <Link href="/products?sort=stock" className="font-medium text-primary underline-offset-4 hover:underline">
                See products by stock
              </Link>
            </p>
          )}
          {estimatedCost !== null && (
            <div className="tabular flex justify-between px-4 pt-3 font-semibold sm:px-5">
              <span>Estimated cost</span>
              <span>{formatPeso(toCents(estimatedCost) / 100)}</span>
            </div>
          )}
          <div className="grid gap-1 px-4 pb-4 pt-3 sm:px-5">
            {canOrder && (
              <div className="mb-2">
                <Button disabled aria-describedby="reorder-pending">
                  Create purchase order
                </Button>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Suggested amount: enough to reach twice the reorder level, or the last {days} days of sales if that is
              more. A simple rule, not a forecast.
            </p>
            {canOrder && (
              <p id="reorder-pending" className="text-xs text-muted-foreground">
                Ordering turns on when purchase orders are built.
              </p>
            )}
          </div>
        </>
      )}
    </Panel>
  );
}

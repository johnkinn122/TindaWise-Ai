import Link from "next/link";
import type { Overview } from "@/lib/api/types";
import { formatNumber, formatPeso } from "@/lib/format";
import { toCents } from "@/lib/money";
import { reorderReason } from "@/lib/overview";
import { CreateOrderFromSuggestionsButton } from "./create-order-button";
import { Panel } from "./panel";

interface ReorderCardProps {
  reorder: Overview["reorder"];
  /** Owners and managers; cashiers see the list without the ordering action. */
  canOrder: boolean;
}

/**
 * Reorder suggestions from each product's recent in-stock sales and delivery time
 * (services/api/app/services/reorder.py). Every line says why it's there.
 * Deliberately a plain Panel, not the Resibo card: that receipt look is reserved for AI output
 * (MASTER.md §7), and this is an average with a safety buffer, not a model.
 */
export function ReorderCard({ reorder, canOrder }: ReorderCardProps) {
  const {
    lines,
    total_count: totalCount,
    window_days: windowDays,
    cover_days: coverDays,
    estimated_cost: estimatedCost,
  } = reorder;
  const hidden = totalCount - lines.length;

  return (
    <Panel title="Reorder suggestions">
      {lines.length === 0 ? (
        <p className="px-4 py-5 text-[0.8125rem] text-muted-foreground sm:px-5">
          Nothing to reorder. Stock and open orders cover expected sales for every product.
        </p>
      ) : (
        <>
          <p className="px-4 pt-3.5 text-[0.8125rem] text-muted-foreground sm:px-5">
            {totalCount === 1 ? "1 item" : `${formatNumber(totalCount)} items`} may run out before a new delivery
            arrives.
          </p>
          <ul className="mt-2 divide-y divide-border border-y border-border text-[0.8125rem]">
            {lines.map((line) => (
              <li key={line.product_id} className="flex items-start justify-between gap-3 px-4 py-2.5 sm:px-5">
                <div className="min-w-0">
                  <p className="font-medium">{line.name}</p>
                  <p className="tabular text-xs text-muted-foreground">{reorderReason(line)}</p>
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
                <CreateOrderFromSuggestionsButton />
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Each amount covers the delivery time plus {coverDays} days at the item&apos;s average daily sales on days
              it was in stock (last {windowDays} days), with a buffer for uneven days, minus stock on hand and on order.
              Items with less than a week of history are ordered up to twice their reorder level.
              {canOrder && (
                <>
                  {" "}
                  <Link href="/suppliers" className="font-medium text-primary underline-offset-4 hover:underline">
                    Set delivery times on suppliers
                  </Link>
                  .
                </>
              )}
            </p>
            {canOrder && (
              <p id="reorder-draft-note" className="text-xs text-muted-foreground">
                Creates a draft with every suggestion at current costs. You choose the supplier; the owner approves.
              </p>
            )}
          </div>
        </>
      )}
    </Panel>
  );
}

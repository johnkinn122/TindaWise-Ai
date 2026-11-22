import { Search, X } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { MovementReason, Person } from "@/lib/api/types";
import { hasFilters, type InventoryParams, inventoryHref } from "@/lib/inventory";
import { movementReasonLabels } from "@/lib/products";

const selectClass = "h-9 rounded-sm border border-input bg-card px-2.5 text-sm text-foreground";
const labelClass = "grid gap-1.5 text-[0.8125rem] font-medium";

interface LedgerFiltersProps {
  params: InventoryParams;
  people: Person[];
  /** Name of the product in `params.product`, when there is one. */
  productName?: string;
}

/**
 * One row above the ledger it scopes. A plain GET form, so every view has a URL (shareable, back
 * button works) and nothing needs JavaScript. Submitting starts from the first page.
 */
export function LedgerFilters({ params, people, productName }: LedgerFiltersProps) {
  return (
    <form role="search" aria-label="Filter stock changes" action="/inventory" method="get" className="grid gap-3 border-b border-border px-4 py-3 sm:px-5">
      <div className="flex flex-wrap items-end gap-3">
        {params.product && <input type="hidden" name="product" value={params.product} />}
        <label className={`${labelClass} min-w-48 flex-1`}>
          Product
          <span className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
            <Input name="q" type="search" defaultValue={params.q} placeholder="Name or SKU" autoComplete="off" className="h-9 bg-card pl-8 font-normal" />
          </span>
        </label>
        <label className={labelClass}>
          Reason
          <select name="reason" defaultValue={params.reason ?? ""} className={selectClass}>
            <option value="">All</option>
            {(Object.entries(movementReasonLabels) as [MovementReason, string][]).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          By
          <select name="who" defaultValue={params.who ?? ""} className={`${selectClass} max-w-48`}>
            <option value="">Anyone</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.name}
              </option>
            ))}
          </select>
        </label>
        {/* The two dates stay together, side by side even on a phone. */}
        <div className="grid w-full grid-cols-2 gap-3 sm:flex sm:w-auto">
          <label className={labelClass}>
            From
            <Input type="date" name="start" defaultValue={params.start} className="h-9 w-full bg-card font-normal sm:w-40" />
          </label>
          <label className={labelClass}>
            To
            <Input type="date" name="end" defaultValue={params.end} className="h-9 w-full bg-card font-normal sm:w-40" />
          </label>
        </div>
        <div className="flex gap-2">
          <Button type="submit" variant="outline">
            Show
          </Button>
          {hasFilters(params) && (
            <Button variant="ghost" asChild>
              <Link href="/inventory">Clear</Link>
            </Button>
          )}
        </div>
      </div>
      {params.product && (
        <p className="flex flex-wrap items-center gap-2 text-[0.8125rem] text-muted-foreground">
          Showing one product:
          <span className="inline-flex items-center gap-1 rounded-sm border border-border bg-muted py-0.5 pl-2 pr-1 font-medium text-foreground">
            {productName ?? "Unknown product"}
            <Link
              href={inventoryHref(params, { product: undefined, page: undefined })}
              aria-label={`Show all products, not just ${productName ?? "this one"}`}
              className="grid size-6 place-items-center rounded-[4px] text-muted-foreground hover:bg-background hover:text-foreground"
            >
              <X className="size-3.5" aria-hidden="true" />
            </Link>
          </span>
        </p>
      )}
    </form>
  );
}

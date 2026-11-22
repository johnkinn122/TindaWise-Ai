import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { LedgerEntry } from "@/lib/api/types";
import { formatDateTime, formatNumber } from "@/lib/format";
import { formatChange, sourceHref, sourceLabel } from "@/lib/inventory";
import { movementReasonLabels } from "@/lib/products";
import { cn } from "@/lib/utils";

/**
 * The store-wide stock ledger. On phones, date, who and source fold under the product so the
 * row keeps the two numbers that matter (change and balance) without scrolling sideways.
 */
export function LedgerTable({ entries }: { entries: LedgerEntry[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="hidden pl-4 sm:table-cell sm:pl-5">When</TableHead>
          <TableHead className="pl-4 sm:pl-2">Product</TableHead>
          <TableHead className="hidden md:table-cell">Reason</TableHead>
          <TableHead className="text-right">Change</TableHead>
          <TableHead className="text-right">Balance</TableHead>
          <TableHead className="hidden xl:table-cell">By</TableHead>
          <TableHead className="hidden pr-4 sm:table-cell sm:pr-5">Source</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const source = entry.source && (
            <Link href={sourceHref(entry.source)} className="tabular font-medium text-primary hover:underline">
              {sourceLabel(entry.source)}
            </Link>
          );
          return (
            <TableRow key={entry.id}>
              <TableCell className="hidden pl-4 align-top text-muted-foreground sm:table-cell sm:pl-5">
                {formatDateTime(entry.created_at)}
                {/* Below xl the "By" column is hidden (the sidebar leaves too little room), so who goes here. */}
                {entry.created_by_name && <div className="text-xs xl:hidden">by {entry.created_by_name}</div>}
              </TableCell>
              <TableCell className="whitespace-normal pl-4 align-top sm:pl-2">
                <Link href={`/products/${entry.product_id}`} className="font-medium hover:underline">
                  {entry.product_name}
                </Link>
                <div className="text-xs text-muted-foreground">
                  {entry.sku}
                  <span className="md:hidden"> · {movementReasonLabels[entry.reason]}</span>
                  <span className="sm:hidden"> · {formatDateTime(entry.created_at)}</span>
                </div>
                {/* Sales, refunds and deliveries note their own number ("Receipt S-000052"); the source link already says that. */}
                {entry.note && !entry.source && <div className="mt-0.5 text-xs text-muted-foreground">{entry.note}</div>}
                {source && <div className="mt-0.5 text-xs sm:hidden">{source}</div>}
              </TableCell>
              <TableCell className="hidden align-top md:table-cell">{movementReasonLabels[entry.reason]}</TableCell>
              <TableCell className={cn("tabular text-right align-top font-medium", entry.quantity_change > 0 ? "text-success" : "text-destructive")}>
                {formatChange(entry.quantity_change)}
              </TableCell>
              <TableCell className="tabular text-right align-top">
                {formatNumber(entry.balance_after)}
                <span className="sr-only"> {entry.unit}</span>
              </TableCell>
              <TableCell className="hidden align-top xl:table-cell">
                {entry.created_by_name ?? <span className="text-muted-foreground">—</span>}
              </TableCell>
              <TableCell className="hidden pr-4 align-top sm:table-cell sm:pr-5">
                {source ?? <span className="text-muted-foreground">—</span>}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { PurchaseOrderSummary } from "@/lib/api/types";
import { formatCalendarDate, formatDate } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";
import { PurchaseOrderStatusBadge } from "./status-badge";

/** `timeZone`: the store's (organization.timezone). */
export function PurchaseOrdersTable({ orders, timeZone }: { orders: PurchaseOrderSummary[]; timeZone: string }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">Order</TableHead>
          <TableHead className="hidden sm:table-cell">Supplier</TableHead>
          <TableHead className="hidden md:table-cell">Expected</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="hidden pr-4 sm:table-cell sm:pr-5">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {orders.map((po) => (
          <TableRow key={po.id} className="relative">
            <TableCell className="whitespace-normal pl-4 sm:pl-5">
              {/* The link covers the whole row, so the row is one big target. */}
              <Link
                href={`/purchase-orders/${po.id}`}
                className="tabular font-medium after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-ring"
              >
                {po.code}
              </Link>
              <div className="text-xs text-muted-foreground">
                {po.line_count === 1 ? "1 product" : `${po.line_count} products`} · {formatDate(po.created_at, timeZone)}
              </div>
              <div className="mt-1 text-xs sm:hidden">{po.supplier?.name ?? "No supplier yet"}</div>
              <div className="mt-1.5 sm:hidden">
                <PurchaseOrderStatusBadge status={po.status} />
              </div>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              {po.supplier?.name ?? <span className="text-muted-foreground">No supplier yet</span>}
            </TableCell>
            <TableCell className="hidden text-muted-foreground md:table-cell">
              {po.expected_on ? formatCalendarDate(po.expected_on) : "—"}
            </TableCell>
            <TableCell className="tabular text-right">{formatCents(toCents(po.total))}</TableCell>
            <TableCell className="hidden pr-4 sm:table-cell sm:pr-5">
              <PurchaseOrderStatusBadge status={po.status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

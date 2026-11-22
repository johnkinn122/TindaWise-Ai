import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { SaleSummary } from "@/lib/api/types";
import { formatDateTime, formatNumber } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";
import { paymentMethodLabels } from "@/lib/sales";
import { RefundStatusBadge } from "./refund-status-badge";

const peso = (amount: string) => formatCents(toCents(amount));

export function SalesTable({ sales, showCashier }: { sales: SaleSummary[]; showCashier: boolean }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">Receipt</TableHead>
          <TableHead className="hidden sm:table-cell">Date</TableHead>
          {showCashier && <TableHead className="hidden lg:table-cell">Cashier</TableHead>}
          <TableHead className="hidden md:table-cell">Payment</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="hidden pr-4 sm:table-cell sm:pr-5">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sales.map((sale) => (
          <TableRow key={sale.id} className="relative">
            <TableCell className="whitespace-normal pl-4 sm:pl-5">
              {/* The link covers the whole row, so the row is one big target. */}
              <Link
                href={`/sales/${sale.id}`}
                className="tabular font-medium after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-ring"
              >
                {sale.receipt_code}
              </Link>
              <div className="text-xs text-muted-foreground">
                {sale.item_count === 1 ? "1 item" : `${formatNumber(sale.item_count)} items`}
                <span className="sm:hidden"> · {formatDateTime(sale.created_at)}</span>
              </div>
              {sale.refund_status !== "none" && (
                <div className="mt-1.5 sm:hidden">
                  <RefundStatusBadge status={sale.refund_status} />
                </div>
              )}
            </TableCell>
            <TableCell className="hidden text-muted-foreground sm:table-cell">{formatDateTime(sale.created_at)}</TableCell>
            {showCashier && (
              <TableCell className="hidden lg:table-cell">{sale.cashier_name ?? <span className="text-muted-foreground">—</span>}</TableCell>
            )}
            <TableCell className="hidden md:table-cell">{paymentMethodLabels[sale.payment_method]}</TableCell>
            <TableCell className="tabular text-right">
              {peso(sale.total)}
              {sale.refund_status !== "none" && (
                <div className="text-xs text-muted-foreground">−{peso(sale.refunded_total)} refunded</div>
              )}
            </TableCell>
            <TableCell className="hidden pr-4 sm:table-cell sm:pr-5">
              {sale.refund_status !== "none" ? <RefundStatusBadge status={sale.refund_status} /> : <span className="sr-only">Paid</span>}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

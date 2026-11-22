import { ArrowDown } from "lucide-react";
import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ReportParams } from "@/lib/api/reports";
import type { ReportProductSort, SalesReport } from "@/lib/api/types";
import { formatNumber, formatPercent } from "@/lib/format";
import { formatCents, signedCents, toCents } from "@/lib/money";
import { productSortLabels, reportQuery } from "@/lib/reports";
import { cn } from "@/lib/utils";

/** Column header that sorts the list (largest first) through the URL; announces the sort. */
function SortHeader({ sort, params, className }: { sort: ReportProductSort; params: ReportParams; className?: string }) {
  const active = (params.sort ?? "sales") === sort;
  return (
    <TableHead aria-sort={active ? "descending" : "none"} className={cn("text-right", className)}>
      <Link
        href={`/reports?${reportQuery(params, { sort: sort === "sales" ? undefined : sort })}`}
        scroll={false}
        className={cn("inline-flex items-center gap-1 hover:text-foreground", active && "text-foreground")}
      >
        {/* Arrow before the label, so the label's right edge lines up with the numbers below. */}
        <ArrowDown className={cn("size-3.5", !active && "opacity-0")} aria-hidden="true" />
        {productSortLabels[sort]}
        {!active && <span className="sr-only">, sort by this</span>}
      </Link>
    </TableHead>
  );
}

export function TopProductsTable({ report, params }: { report: SalesReport; params: ReportParams }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">Product</TableHead>
          <SortHeader sort="quantity" params={params} className="hidden sm:table-cell" />
          <SortHeader sort="sales" params={params} />
          <SortHeader sort="gross_profit" params={params} className="hidden md:table-cell" />
          <TableHead className="hidden pr-4 text-right sm:pr-5 lg:table-cell">Margin</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {report.products.map((product, index) => (
          <TableRow key={product.product_id}>
            <TableCell className="whitespace-normal pl-4 sm:pl-5">
              <span className="mr-2 tabular text-xs text-muted-foreground">{index + 1}.</span>
              <Link href={`/products/${product.product_id}`} className="font-medium hover:underline">
                {product.name}
              </Link>
              <div className="pl-5 text-xs text-muted-foreground">{product.sku}</div>
            </TableCell>
            <TableCell className="tabular hidden text-right sm:table-cell">
              {formatNumber(product.quantity)}
              <span className="ml-1 text-xs text-muted-foreground">{product.unit}</span>
            </TableCell>
            <TableCell className="tabular text-right">{formatCents(toCents(product.sales))}</TableCell>
            <TableCell className="tabular hidden text-right md:table-cell">{formatCents(signedCents(product.gross_profit))}</TableCell>
            <TableCell className="tabular hidden pr-4 text-right sm:pr-5 lg:table-cell">
              {product.gross_margin === null ? "—" : formatPercent(Number(product.gross_margin))}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

import Link from "next/link";
import { StockBadge } from "@/components/dashboard/stock-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Product } from "@/lib/api/types";
import { formatNumber, formatPeso } from "@/lib/format";

export function ProductsTable({ products }: { products: Product[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">Product</TableHead>
          <TableHead className="hidden md:table-cell">Category</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead className="text-right">On hand</TableHead>
          <TableHead className="hidden pr-4 sm:table-cell sm:pr-5">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {products.map((product) => (
          <TableRow key={product.id} className="relative">
            <TableCell className="whitespace-normal pl-4 sm:pl-5">
              {/* The link covers the whole row (after: pseudo-element), so the row is one big target. */}
              <Link
                href={`/products/${product.id}`}
                className="font-medium after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-ring"
              >
                {product.name}
              </Link>
              <div className="text-xs text-muted-foreground">{product.sku}</div>
              {/* Status column is hidden on phones; show the badge here instead. */}
              <div className="mt-1.5 sm:hidden">
                <StockBadge status={product.stock_status} />
              </div>
            </TableCell>
            <TableCell className="hidden text-muted-foreground md:table-cell">
              {product.category?.name ?? "—"}
            </TableCell>
            <TableCell className="text-right">{formatPeso(Number(product.price))}</TableCell>
            <TableCell className="text-right">
              {formatNumber(product.stock_on_hand)}
              <span className="ml-1 text-xs text-muted-foreground">{product.unit}</span>
            </TableCell>
            <TableCell className="hidden pr-4 sm:table-cell sm:pr-5">
              <StockBadge status={product.stock_status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

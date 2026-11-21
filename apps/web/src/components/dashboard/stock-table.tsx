import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatNumber } from "@/lib/format";
import type { StockItem } from "@/lib/sample-data";
import { StockBadge } from "./stock-badge";

export function StockTable({ items }: { items: StockItem[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">Product</TableHead>
          <TableHead className="hidden sm:table-cell">Category</TableHead>
          <TableHead className="text-right">On hand</TableHead>
          <TableHead className="pr-4 sm:pr-5">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="whitespace-normal pl-4 sm:pl-5">{item.name}</TableCell>
            <TableCell className="hidden text-muted-foreground sm:table-cell">{item.category}</TableCell>
            <TableCell className="text-right">{formatNumber(item.onHand)}</TableCell>
            <TableCell className="pr-4 sm:pr-5">
              <StockBadge status={item.status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

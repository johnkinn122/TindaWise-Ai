import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { StockMovement } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import { movementReasonLabels } from "@/lib/products";
import { cn } from "@/lib/utils";

const dateFormatter = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Manila",
});

export function MovementHistory({ movements }: { movements: StockMovement[] }) {
  if (movements.length === 0) {
    return <p className="px-4 py-6 text-muted-foreground sm:px-5">No stock changes yet.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">When</TableHead>
          <TableHead>Reason</TableHead>
          <TableHead className="text-right">Change</TableHead>
          <TableHead className="pr-4 text-right sm:pr-5">Balance</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {movements.map((movement) => (
          <TableRow key={movement.id}>
            <TableCell className="pl-4 text-muted-foreground sm:pl-5">
              {dateFormatter.format(new Date(movement.created_at))}
            </TableCell>
            <TableCell className="whitespace-normal">
              {movementReasonLabels[movement.reason]}
              {movement.note && <div className="text-xs text-muted-foreground">{movement.note}</div>}
            </TableCell>
            <TableCell
              className={cn(
                "text-right font-medium",
                movement.quantity_change > 0 ? "text-success" : "text-destructive",
              )}
            >
              {movement.quantity_change > 0 ? "+" : "−"}
              {formatNumber(Math.abs(movement.quantity_change))}
            </TableCell>
            <TableCell className="pr-4 text-right sm:pr-5">{formatNumber(movement.balance_after)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

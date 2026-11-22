import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Supplier } from "@/lib/api/types";

export function SuppliersTable({ suppliers }: { suppliers: Supplier[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-4 sm:pl-5">Supplier</TableHead>
          <TableHead className="hidden sm:table-cell">Contact</TableHead>
          <TableHead className="pr-4 sm:pr-5">Phone</TableHead>
          <TableHead className="hidden pr-4 text-right lg:table-cell lg:pr-5">Delivery</TableHead>
          <TableHead className="hidden pr-4 md:table-cell md:pr-5">Email</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {suppliers.map((supplier) => (
          <TableRow key={supplier.id} className="relative">
            <TableCell className="whitespace-normal pl-4 sm:pl-5">
              {/* The link covers the whole row, so the row is one big target. */}
              <Link
                href={`/suppliers/${supplier.id}/edit`}
                className="font-medium after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-ring"
              >
                {supplier.name}
              </Link>
              {supplier.notes && <div className="line-clamp-1 text-xs text-muted-foreground">{supplier.notes}</div>}
            </TableCell>
            <TableCell className="hidden text-muted-foreground sm:table-cell">{supplier.contact_name ?? "—"}</TableCell>
            <TableCell className="pr-4 tabular sm:pr-5">{supplier.phone ?? "—"}</TableCell>
            <TableCell className="hidden pr-4 text-right tabular text-muted-foreground lg:table-cell lg:pr-5">
              {supplier.lead_time_days === null
                ? "Default"
                : `${supplier.lead_time_days} ${supplier.lead_time_days === 1 ? "day" : "days"}`}
            </TableCell>
            <TableCell className="hidden pr-4 text-muted-foreground md:table-cell md:pr-5">{supplier.email ?? "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

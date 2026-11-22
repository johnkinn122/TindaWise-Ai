"use client";

import { Printer } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import type { Sale } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";

/**
 * The customer's receipt. Plain on purpose: the zig-zag "Resibo" style is reserved for AI
 * suggestions (MASTER.md §7). Printing shows only this block (see .print-receipt in globals.css).
 */
export function Receipt({
  sale,
  storeName,
  timeZone,
  onNewSale,
}: {
  sale: Sale;
  storeName: string;
  /** The store's time zone: the receipt shows the sale's local time. */
  timeZone: string;
  onNewSale: () => void;
}) {
  const newSaleRef = useRef<HTMLButtonElement>(null);
  useEffect(() => newSaleRef.current?.focus(), []);

  return (
    <div className="mx-auto grid max-w-md gap-4">
      <section
        aria-labelledby="receipt-title"
        className="print-receipt rounded-lg border border-border bg-card px-5 py-6 text-sm"
      >
        <header className="text-center">
          <p className="font-display text-lg font-semibold">{storeName}</p>
          <h2 id="receipt-title" className="mt-1 font-medium">
            Receipt {sale.receipt_code}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatDateTime(sale.created_at, timeZone)}
            {sale.cashier_name && <> · Cashier: {sale.cashier_name}</>}
          </p>
        </header>

        <table className="mt-5 w-full border-y border-dashed border-border">
          <caption className="sr-only">Items</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Item</th>
              <th scope="col">Amount</th>
            </tr>
          </thead>
          <tbody>
            {sale.lines.map((line) => (
              <tr key={line.product_id} className="align-top">
                <td className="py-2 pr-3">
                  <div>{line.product_name}</div>
                  <div className="tabular text-xs text-muted-foreground">
                    {line.quantity} × {formatCents(toCents(line.unit_price))}
                  </div>
                </td>
                <td className="tabular py-2 text-right">{formatCents(toCents(line.line_total))}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <dl className="mt-3 grid gap-1">
          <div className="flex justify-between text-base font-semibold">
            <dt>Total</dt>
            <dd className="tabular">{formatCents(toCents(sale.total))}</dd>
          </div>
          {sale.payment_method === "cash" ? (
            <>
              <div className="flex justify-between text-muted-foreground">
                <dt>Cash</dt>
                <dd className="tabular">{formatCents(toCents(sale.amount_tendered ?? "0"))}</dd>
              </div>
              <div className="flex justify-between font-medium">
                <dt>Change</dt>
                <dd className="tabular">{formatCents(toCents(sale.change_due ?? "0"))}</dd>
              </div>
            </>
          ) : (
            <div className="flex justify-between text-muted-foreground">
              <dt>E-wallet reference</dt>
              <dd>{sale.payment_reference}</dd>
            </div>
          )}
        </dl>
        <p className="mt-5 text-center text-xs text-muted-foreground">
          {sale.item_count} {sale.item_count === 1 ? "item" : "items"} · Thank you!
        </p>
      </section>

      <div className="grid grid-cols-2 gap-2">
        <Button variant="outline" size="lg" onClick={() => window.print()}>
          <Printer aria-hidden="true" />
          Print receipt
        </Button>
        <Button ref={newSaleRef} size="lg" onClick={onNewSale}>
          New sale
        </Button>
      </div>
    </div>
  );
}

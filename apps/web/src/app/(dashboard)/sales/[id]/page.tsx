import { CircleCheck, Undo2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ApiErrorState } from "@/components/products/api-error-state";
import { RefundStatusBadge } from "@/components/sales/refund-status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getSale } from "@/lib/api/sales";
import type { Sale } from "@/lib/api/types";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { formatDateTime, formatNumber } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";
import { canRefund, payBackWording, paymentMethodLabels, refundReasonLabels } from "@/lib/sales";

export const metadata: Metadata = {
  title: "Receipt",
};

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
const peso = (amount: string) => formatCents(toCents(amount));

export default function SalePage({ params, searchParams }: PageProps<"/sales/[id]">) {
  return (
    <div className="grid gap-5">
      <Suspense fallback={<ReceiptSkeleton />}>
        <Receipt params={params} searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Receipt({
  params,
  searchParams,
}: {
  params: PageProps<"/sales/[id]">["params"];
  searchParams: PageProps<"/sales/[id]">["searchParams"];
}) {
  const { id } = await params;
  const me = await getCurrentUser();
  let sale: Sale;
  try {
    sale = await getSale(id);
  } catch (error) {
    // 404 also covers another cashier's receipt: the API doesn't reveal that it exists.
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) {
      return <ApiErrorState retryHref={`/sales/${id}`} title="Can't load the receipt" />;
    }
    throw error;
  }

  const manager = canManageInventory(me.role);
  const refundedCode = first((await searchParams).refunded);
  const justRefunded = sale.refunds.find((refund) => refund.refund_code === refundedCode);
  const refunded = sale.refund_status !== "none";

  return (
    <>
      <PageHeader
        title={`Receipt ${sale.receipt_code}`}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            <RefundStatusBadge status={sale.refund_status} />
            {formatDateTime(sale.created_at)}
            {sale.cashier_name && <> · {sale.cashier_name}</>}
          </span>
        }
        action={
          canRefund(sale, manager) ? (
            <Button variant="outline" asChild>
              <Link href={`/sales/${sale.id}/refund`}>
                <Undo2 aria-hidden="true" />
                Refund items
              </Link>
            </Button>
          ) : undefined
        }
      />

      {justRefunded && (
        <p role="status" className="flex items-start gap-2 rounded-sm border border-success/40 bg-success/10 px-3 py-2.5 text-sm">
          <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
          <span>
            <span className="font-medium">Refund {justRefunded.refund_code} recorded.</span> Give back{" "}
            <span className="tabular font-semibold">{peso(justRefunded.total)}</span> {payBackWording[justRefunded.payment_method]}.
          </span>
        </p>
      )}
      {!manager && sale.refund_status !== "full" && (
        <RoleNotice>Refunds are given by an owner or manager. Ask them to open this receipt.</RoleNotice>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="grid min-w-0 gap-5 lg:col-span-8">
          <Panel title="Items">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-4 sm:pl-5">Item</TableHead>
                  <TableHead className="text-right">Sold</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">Refunded</TableHead>
                  <TableHead className="hidden text-right md:table-cell">Price</TableHead>
                  <TableHead className="pr-4 text-right sm:pr-5">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sale.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="whitespace-normal pl-4 sm:pl-5">
                      <div className="font-medium">{line.product_name}</div>
                      <div className="text-xs text-muted-foreground">{line.sku}</div>
                      {line.quantity_refunded > 0 && (
                        <div className="tabular text-xs text-muted-foreground sm:hidden">
                          {formatNumber(line.quantity_refunded)} refunded
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="tabular text-right">
                      {formatNumber(line.quantity)}
                      <span className="ml-1 text-xs text-muted-foreground">{line.unit}</span>
                    </TableCell>
                    <TableCell className="tabular hidden text-right sm:table-cell">
                      {line.quantity_refunded > 0 ? formatNumber(line.quantity_refunded) : <span className="text-muted-foreground">—</span>}
                    </TableCell>
                    <TableCell className="tabular hidden text-right md:table-cell">{peso(line.unit_price)}</TableCell>
                    <TableCell className="tabular pr-4 text-right sm:pr-5">{peso(line.line_total)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TotalRow label="Total" amount={peso(sale.total)} strong={!refunded} />
                {refunded && (
                  <>
                    <TotalRow label="Refunded" amount={`−${peso(sale.refunded_total)}`} />
                    <TotalRow label="Kept" amount={formatCents(toCents(sale.total) - toCents(sale.refunded_total))} strong />
                  </>
                )}
              </TableFooter>
            </Table>
          </Panel>

          {sale.refunds.length > 0 && (
            <Panel title="Refunds">
              <ol className="divide-y divide-border">
                {sale.refunds.map((refund) => (
                  <li key={refund.id} className="grid gap-1 px-4 py-3 text-sm sm:px-5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                      <p className="font-medium">
                        {refund.refund_code} · {refundReasonLabels[refund.reason]}
                      </p>
                      <p className="tabular font-semibold">−{peso(refund.total)}</p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {formatDateTime(refund.created_at)}
                      {refund.refunded_by_name && ` · ${refund.refunded_by_name}`} · paid back {payBackWording[refund.payment_method]}
                    </p>
                    <ul className="mt-1 text-muted-foreground">
                      {refund.lines.map((line) => (
                        <li key={line.sale_line_id} className="tabular">
                          {formatNumber(line.quantity)} × {line.product_name}{" "}
                          <span className="text-xs">· {line.restocked ? "back in stock" : "not restocked"}</span>
                        </li>
                      ))}
                    </ul>
                    {refund.note && <p className="text-xs text-muted-foreground">Note: {refund.note}</p>}
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </div>

        <div className="grid min-w-0 gap-5 lg:col-span-4">
          <Panel title="Payment">
            <dl className="divide-y divide-border text-sm">
              <Fact label="Method" value={paymentMethodLabels[sale.payment_method]} />
              {sale.payment_method === "cash" ? (
                <>
                  <Fact label="Cash received" value={peso(sale.amount_tendered ?? "0")} />
                  <Fact label="Change" value={peso(sale.change_due ?? "0")} />
                </>
              ) : (
                <Fact label="Reference" value={sale.payment_reference ?? "—"} />
              )}
              <Fact label="Items" value={formatNumber(sale.item_count)} />
              <Fact label="Cashier" value={sale.cashier_name ?? "—"} />
            </dl>
          </Panel>
          <Button variant="ghost" className="justify-self-start" asChild>
            <Link href="/sales">Back to sales history</Link>
          </Button>
        </div>
      </div>
    </>
  );
}

function TotalRow({ label, amount, strong = false }: { label: string; amount: string; strong?: boolean }) {
  return (
    <TableRow className="hover:bg-transparent">
      <TableCell colSpan={2} className={strong ? "pl-4 font-semibold sm:pl-5" : "pl-4 text-muted-foreground sm:pl-5"}>
        {label}
      </TableCell>
      <TableCell className="hidden sm:table-cell" />
      <TableCell className="hidden md:table-cell" />
      <TableCell className={strong ? "tabular pr-4 text-right font-semibold sm:pr-5" : "tabular pr-4 text-right text-muted-foreground sm:pr-5"}>
        {amount}
      </TableCell>
    </TableRow>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 px-4 py-3 sm:px-5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

function ReceiptSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading receipt" className="grid gap-5">
      <Skeleton className="h-12 w-72 max-w-full" />
      <div className="grid gap-5 lg:grid-cols-12">
        <Skeleton className="h-80 lg:col-span-8" />
        <Skeleton className="h-64 lg:col-span-4" />
      </div>
    </div>
  );
}

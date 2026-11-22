import { BarChart3, Download } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ApiErrorState } from "@/components/products/api-error-state";
import { BarList } from "@/components/reports/bar-list";
import { ReportFilters } from "@/components/reports/report-filters";
import { SalesColumns } from "@/components/reports/sales-columns";
import { TopProductsTable } from "@/components/reports/top-products-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getSalesReport } from "@/lib/api/reports";
import type { SalesReport } from "@/lib/api/types";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { formatNumber, formatPercent } from "@/lib/format";
import { formatCents, signedCents, toCents } from "@/lib/money";
import {
  buildReportKpis,
  buildSeries,
  type ExportKind,
  formatPeriod,
  granularityLabels,
  parseReportParams,
  paymentLabels,
  refundBreakdown,
  reportQuery,
  seriesSummary,
} from "@/lib/reports";

export const metadata: Metadata = {
  title: "Reports",
};

const peso = (amount: string) => formatCents(signedCents(amount));

export default function ReportsPage({ searchParams }: PageProps<"/reports">) {
  return (
    <div className="grid gap-5">
      <PageHeader title="Reports" description="Sales, profit and purchases for any period, compared with the period before." />
      <Suspense fallback={<ReportSkeleton />}>
        <Report searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Report({ searchParams }: { searchParams: PageProps<"/reports">["searchParams"] }) {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return <RoleNotice>Reports show costs and profit, so only owners and managers can see them.</RoleNotice>;
  }
  const params = parseReportParams(await searchParams);
  let report: SalesReport;
  try {
    report = await getSalesReport(params);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      // A custom range the API refused (end before start, over a year): say why, keep the filters.
      return (
        <div className="grid gap-4">
          <RoleNotice>{error.message}</RoleNotice>
          <ReportFilters params={params} period={{ start: params.start ?? "", end: params.end ?? "", days: 0 }} />
        </div>
      );
    }
    if (error instanceof ApiUnavailableError) {
      return (
        <section aria-label="Report" className="rounded-lg border border-border bg-card">
          <ApiErrorState retryHref={`/reports?${reportQuery(params)}`} title="Can't load the report" />
        </section>
      );
    }
    throw error;
  }

  // A period with only refunds still has something to show (negative net sales).
  const hasSales = report.summary.transactions > 0 || report.summary.refund_count > 0;
  const exportHref = (kind: ExportKind) => {
    const query = new URLSearchParams(reportQuery(params));
    query.set("kind", kind);
    return `/reports/export?${query.toString()}`;
  };
  const csv = (kind: ExportKind, label: string) => (
    <Button variant="outline" asChild>
      {/* A plain link with `download`: the route answers with a file, not a page. */}
      <a href={exportHref(kind)} download>
        <Download aria-hidden="true" />
        {label}
      </a>
    </Button>
  );
  const totalSalesCents = signedCents(report.summary.sales);
  const breakdown = refundBreakdown(report);

  return (
    <>
      <ReportFilters params={params} period={report.period} />
      <p className="-mt-1 text-[0.8125rem] text-muted-foreground">
        <span className="font-medium text-foreground">{formatPeriod(report.period)}</span>
        {report.period.days > 1 && ` · ${formatNumber(report.period.days)} days`} · compared with{" "}
        {formatPeriod(report.previous_period)}
      </p>

      <KpiStrip kpis={buildReportKpis(report)} />
      {breakdown && <p className="tabular -mt-2 text-[0.8125rem] text-muted-foreground">{breakdown}</p>}

      {!hasSales ? (
        <section aria-label="No sales" className="grid place-items-center rounded-lg border border-border bg-card px-6 py-14 text-center">
          <BarChart3 className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 font-display text-xl font-semibold">No sales in this period</h2>
          <p className="mt-1.5 max-w-md text-muted-foreground">Choose a longer period, or come back after a few sales.</p>
        </section>
      ) : (
        <>
          <div className="grid items-start gap-5 lg:grid-cols-12">
            <div className="min-w-0 lg:col-span-8">
              <SalesColumns
                title={`Net sales ${granularityLabels[report.granularity]}`}
                rows={buildSeries(report)}
                summary={seriesSummary(report)}
                bucketName={{ day: "Day", week: "Week", month: "Month" }[report.granularity]}
                action={csv("sales", "CSV")}
              />
            </div>
            <div className="grid min-w-0 gap-5 lg:col-span-4">
              <Panel title="Payment methods">
                <BarList
                  label="Net sales by payment method"
                  items={report.payments.map((payment) => ({
                    key: payment.method,
                    label: paymentLabels[payment.method],
                    value: signedCents(payment.sales),
                    display: formatCents(signedCents(payment.sales)),
                    detail: [
                      // A share of a zero or negative total means nothing, so it's left out.
                      totalSalesCents > 0 && `${formatPercent(signedCents(payment.sales) / totalSalesCents, 0)} of sales`,
                      `${formatNumber(payment.transactions)} ${payment.transactions === 1 ? "sale" : "sales"}`,
                      toCents(payment.refunds) > 0 && `${peso(payment.refunds)} refunded`,
                    ]
                      .filter(Boolean)
                      .join(" · "),
                  }))}
                />
              </Panel>
              <Panel title="Net sales by category" action={csv("categories", "CSV")}>
                <BarList
                  label="Net sales by category"
                  items={report.categories.map((category) => ({
                    key: category.category_id ?? "none",
                    label: category.name,
                    value: signedCents(category.sales),
                    display: formatCents(signedCents(category.sales)),
                    detail: `Profit ${peso(category.gross_profit)} · ${formatNumber(category.quantity)} sold`,
                  }))}
                />
              </Panel>
            </div>
          </div>

          <Panel title="Top products" action={csv("products", "Download all (CSV)")}>
            <TopProductsTable report={report} params={params} />
            {report.product_count > report.products.length && (
              <p className="border-t border-border px-4 py-3 text-[0.8125rem] text-muted-foreground sm:px-5">
                Showing the top {report.products.length} of {formatNumber(report.product_count)} products sold. The CSV has all of them.
              </p>
            )}
          </Panel>
        </>
      )}

      <Panel title="Purchases received" action={report.suppliers.length > 0 ? csv("suppliers", "CSV") : undefined}>
        {report.suppliers.length === 0 ? (
          <p className="px-4 py-5 text-[0.8125rem] text-muted-foreground sm:px-5">
            No deliveries were received on purchase orders in this period.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4 sm:pl-5">Supplier</TableHead>
                <TableHead className="text-right">Deliveries</TableHead>
                <TableHead className="pr-4 text-right sm:pr-5">Received value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.suppliers.map((supplier) => (
                <TableRow key={supplier.supplier_id}>
                  <TableCell className="whitespace-normal pl-4 font-medium sm:pl-5">{supplier.name}</TableCell>
                  <TableCell className="tabular text-right">{formatNumber(supplier.deliveries)}</TableCell>
                  <TableCell className="tabular pr-4 text-right sm:pr-5">{peso(supplier.received_value)}</TableCell>
                </TableRow>
              ))}
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={2} className="pl-4 font-semibold sm:pl-5">
                  Total
                </TableCell>
                <TableCell className="tabular pr-4 text-right font-semibold sm:pr-5">{peso(report.purchases_total)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        )}
      </Panel>
    </>
  );
}

function ReportSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading report" className="grid gap-5">
      <Skeleton className="h-11 w-full max-w-3xl" />
      <Skeleton className="h-[7.5rem] rounded-lg lg:h-[6.75rem]" />
      <div className="grid gap-5 lg:grid-cols-12">
        <Skeleton className="h-80 rounded-lg lg:col-span-8" />
        <Skeleton className="h-80 rounded-lg lg:col-span-4" />
      </div>
      <Skeleton className="h-72 rounded-lg" />
    </div>
  );
}

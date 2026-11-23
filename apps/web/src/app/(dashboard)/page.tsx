import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ReorderCard } from "@/components/dashboard/reorder-card";
import { SalesChart } from "@/components/dashboard/sales-chart";
import { StockTable } from "@/components/dashboard/stock-table";
import { WorthALook } from "@/components/dashboard/worth-a-look";
import { ApiErrorState } from "@/components/products/api-error-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { getOverview } from "@/lib/api/overview";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { buildKpis, buildStockItems, buildWeeklySales, weeklySummary } from "@/lib/overview";

export const metadata: Metadata = {
  title: "Overview",
};

/** The header is static; the figures stream in behind Suspense (they depend on who is signed in). */
export default function OverviewPage() {
  return (
    <div className="grid gap-5">
      <PageHeader title="Overview" description="What is selling, what is running low, and what to do next." />
      <Suspense fallback={<OverviewSkeleton />}>
        <OverviewContent />
      </Suspense>
    </div>
  );
}

async function OverviewContent() {
  let overview;
  let me;
  try {
    [overview, me] = await Promise.all([getOverview(), getCurrentUser()]);
  } catch (error) {
    if (error instanceof ApiUnavailableError) {
      return (
        <section aria-label="Overview" className="rounded-lg border border-border bg-card">
          <ApiErrorState retryHref="/" title="Can't load the overview" />
        </section>
      );
    }
    throw error;
  }

  const mine = overview.sales_scope === "mine";
  const stockItems = buildStockItems(overview.stock_to_watch);
  const notShown = overview.low_stock_count + overview.out_of_stock_count - stockItems.length;

  return (
    <>
      <KpiStrip kpis={buildKpis(overview)} />

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="grid min-w-0 gap-5 lg:col-span-8">
          <SalesChart
            title={mine ? "Your sales this week" : "Sales this week"}
            data={buildWeeklySales(overview)}
            summary={weeklySummary(overview)}
          />
          <Panel
            title="Stock to watch"
            action={
              notShown > 0 ? (
                <Button variant="outline" asChild>
                  <Link href="/products?sort=stock">View all {overview.low_stock_count + overview.out_of_stock_count}</Link>
                </Button>
              ) : undefined
            }
          >
            {stockItems.length > 0 ? (
              <StockTable items={stockItems} />
            ) : (
              <p className="px-4 py-5 text-[0.8125rem] text-muted-foreground sm:px-5">
                Every product is above its reorder level.
              </p>
            )}
          </Panel>
        </div>
        {/* On small screens the reorder list comes right after the KPIs: it is the "what to do next". */}
        <div className="order-first grid min-w-0 gap-5 lg:order-none lg:col-span-4">
          <ReorderCard reorder={overview.reorder} canOrder={canManageInventory(me.role)} />
          {/* Owners and managers only: an alert can point at a cashier's own missing sales. */}
          {canManageInventory(me.role) && (
            <Suspense fallback={<Skeleton aria-label="Loading unusual sales days" className="h-48 rounded-lg" />}>
              <WorthALook />
            </Suspense>
          )}
        </div>
      </div>
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading overview" className="grid gap-5">
      <Skeleton className="h-[7.5rem] rounded-lg lg:h-[6.75rem]" />
      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="grid gap-5 lg:col-span-8">
          <Skeleton className="h-80 rounded-lg" />
          <Skeleton className="h-56 rounded-lg" />
        </div>
        <Skeleton className="h-72 rounded-lg lg:col-span-4" />
      </div>
    </div>
  );
}

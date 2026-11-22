import { Boxes } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { PageHeader } from "@/components/dashboard/page-header";
import { LedgerFilters } from "@/components/inventory/ledger-filters";
import { LedgerTable } from "@/components/inventory/ledger-table";
import { ApiErrorState } from "@/components/products/api-error-state";
import { Pagination } from "@/components/products/pagination";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getInventorySummary, LEDGER_PAGE_SIZE, listLedger } from "@/lib/api/inventory";
import { getProduct } from "@/lib/api/products";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { buildInventoryKpis, hasFilters, type InventoryParams, inventoryFilters, inventoryHref, parseInventoryParams } from "@/lib/inventory";

export const metadata: Metadata = {
  title: "Inventory",
};

export default function InventoryPage({ searchParams }: PageProps<"/inventory">) {
  return (
    <div className="grid gap-5">
      <PageHeader title="Inventory" description="Stock on hand and every change to it: sales, refunds, deliveries and adjustments." />
      <Suspense fallback={<InventorySkeleton />}>
        <Inventory searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

/** A product named in the URL, for the filter chip. A product from another store is a 404: no name. */
async function productName(id: string | undefined): Promise<string | undefined> {
  if (!id) return undefined;
  try {
    return (await getProduct(id)).name;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return undefined;
    throw error;
  }
}

async function Inventory({ searchParams }: { searchParams: PageProps<"/inventory">["searchParams"] }) {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <RoleNotice>
        The inventory ledger shows stock value at cost and who changed stock, so only owners and managers can see it. Stock levels are
        on the <Link href="/products" className="font-medium text-foreground underline">Products</Link> page.
      </RoleNotice>
    );
  }

  const raw = await searchParams;
  const params = parseInventoryParams(raw);
  // The filter form is a plain GET form, so it submits empty fields too (?q=&who=…). Drop them
  // so the URL that gets shared or bookmarked only says what is actually filtered.
  if (Object.values(raw).some((value) => value === "")) {
    redirect(inventoryHref(params, { page: params.page > 1 ? String(params.page) : undefined }));
  }
  let summary, ledger, name;
  try {
    [summary, ledger, name] = await Promise.all([getInventorySummary(), listLedger(params), productName(params.product)]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      // A date range the API refused (end before start): say why and keep the filters to fix it.
      return (
        <section aria-label="Stock changes" className="rounded-lg border border-border bg-card">
          <LedgerFilters params={params} people={[]} />
          <p role="alert" className="px-4 py-6 text-sm text-destructive sm:px-5">
            {error.message}
          </p>
        </section>
      );
    }
    if (error instanceof ApiUnavailableError) {
      return (
        <section aria-label="Stock changes" className="rounded-lg border border-border bg-card">
          <ApiErrorState retryHref={inventoryHref(params)} title="Can't load inventory" />
        </section>
      );
    }
    throw error;
  }

  return (
    <>
      <KpiStrip kpis={buildInventoryKpis(summary)} />
      {/* min-w-0: a grid item is as wide as its content by default, so the wide table would widen the page. */}
      <section aria-labelledby="ledger-heading" className="min-w-0 rounded-lg border border-border bg-card">
        <h2 id="ledger-heading" className="px-4 pt-4 font-display text-lg font-semibold sm:px-5">
          Stock changes
        </h2>
        <LedgerFilters params={params} people={summary.people} productName={name} />
        {ledger.items.length > 0 ? (
          <>
            <LedgerTable entries={ledger.items} />
            <div className="border-t border-border">
              <Pagination
                page={params.page}
                pageSize={LEDGER_PAGE_SIZE}
                total={ledger.total}
                searchParams={inventoryFilters(params)}
                basePath="/inventory"
              />
            </div>
          </>
        ) : (
          <EmptyLedger params={params} />
        )}
      </section>
    </>
  );
}

function EmptyLedger({ params }: { params: InventoryParams }) {
  const filtered = hasFilters(params);
  return (
    <div className="grid place-items-center px-6 py-14 text-center">
      <Boxes className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
      <h3 className="mt-4 font-display text-xl font-semibold">{filtered ? "No stock changes match" : "No stock changes yet"}</h3>
      <p className="mt-1.5 max-w-md text-muted-foreground">
        {filtered
          ? "Try a longer date range or fewer filters."
          : "Changes appear here when you add products, sell, take refunds, receive deliveries or adjust stock."}
      </p>
      <Button className="mt-5" variant={filtered ? "outline" : "default"} asChild>
        {filtered ? <Link href="/inventory">Clear filters</Link> : <Link href="/products/new">Add a product</Link>}
      </Button>
    </div>
  );
}

function InventorySkeleton() {
  return (
    <>
      <Skeleton className="h-[106px] rounded-lg" />
      <Skeleton className="h-96 rounded-lg" />
    </>
  );
}

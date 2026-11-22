import { ClipboardList, Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { Pagination } from "@/components/products/pagination";
import { PurchaseOrdersTable } from "@/components/purchase-orders/purchase-orders-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { listPurchaseOrders, PURCHASE_ORDERS_PAGE_SIZE } from "@/lib/api/purchase-orders";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { findStatusFilter, statusFilters } from "@/lib/purchase-orders";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Purchase orders",
};

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

export default function PurchaseOrdersPage({ searchParams }: PageProps<"/purchase-orders">) {
  return (
    <div className="grid gap-5">
      <PageHeader
        title="Purchase orders"
        description="Draft what to buy, get the owner's approval, then record deliveries as they arrive."
        action={
          <Suspense fallback={null}>
            <NewOrderButton />
          </Suspense>
        }
      />
      <section aria-label="Purchase order list" className="rounded-lg border border-border bg-card">
        <Suspense fallback={<Skeleton className="h-72 rounded-lg" />}>
          <OrderList searchParams={searchParams} />
        </Suspense>
      </section>
    </div>
  );
}

async function NewOrderButton() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) return null;
  return (
    <Button size="lg" asChild>
      <Link href="/purchase-orders/new">
        <Plus aria-hidden="true" />
        New purchase order
      </Link>
    </Button>
  );
}

async function OrderList({ searchParams }: { searchParams: PageProps<"/purchase-orders">["searchParams"] }) {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <div className="p-4 sm:p-5">
        <RoleNotice>Only owners and managers can see purchase orders.</RoleNotice>
      </div>
    );
  }
  const raw = await searchParams;
  const filter = findStatusFilter(first(raw.status));
  const page = Math.max(1, Number.parseInt(first(raw.page) ?? "1", 10) || 1);
  const kept: Record<string, string> = filter.id === "all" ? {} : { status: filter.id };

  let result;
  try {
    result = await listPurchaseOrders({ statuses: [...filter.statuses], page });
  } catch (error) {
    if (error instanceof ApiUnavailableError) {
      return <ApiErrorState retryHref="/purchase-orders" title="Can't load purchase orders" />;
    }
    throw error;
  }

  return (
    <>
      <nav aria-label="Filter by status" className="flex gap-1 overflow-x-auto border-b border-border px-3 py-2.5 sm:px-4">
        {statusFilters.map((option) => {
          const active = option.id === filter.id;
          return (
            <Link
              key={option.id}
              href={option.id === "all" ? "/purchase-orders" : `/purchase-orders?status=${option.id}`}
              aria-current={active ? "page" : undefined}
              className={cn(
                "whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium",
                active ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
            >
              {option.label}
            </Link>
          );
        })}
      </nav>
      {result.items.length > 0 ? (
        <>
          <PurchaseOrdersTable orders={result.items} />
          <div className="border-t border-border">
            <Pagination
              page={page}
              pageSize={PURCHASE_ORDERS_PAGE_SIZE}
              total={result.total}
              searchParams={kept}
              basePath="/purchase-orders"
            />
          </div>
        </>
      ) : (
        <div className="grid place-items-center px-6 py-14 text-center">
          <ClipboardList className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 font-display text-xl font-semibold">
            {filter.id === "all" ? "No purchase orders yet" : `No ${filter.label.toLowerCase()} orders`}
          </h2>
          <p className="mt-1.5 max-w-md text-muted-foreground">
            Start one here, or from the reorder suggestions on the Overview.
          </p>
          <Button className="mt-5" asChild>
            <Link href="/purchase-orders/new">New purchase order</Link>
          </Button>
        </div>
      )}
    </>
  );
}

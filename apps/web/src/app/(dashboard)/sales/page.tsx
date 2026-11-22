import { ReceiptText, Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { Pagination } from "@/components/products/pagination";
import { SalesTable } from "@/components/sales/sales-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { listSales, SALES_PAGE_SIZE } from "@/lib/api/sales";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { normalizeReceiptQuery } from "@/lib/sales";

export const metadata: Metadata = {
  title: "Sales history",
};

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

export default function SalesPage({ searchParams }: PageProps<"/sales">) {
  return (
    <div className="grid gap-5">
      <Suspense fallback={<PageHeader title="Sales history" />}>
        <Header />
      </Suspense>
      <section aria-label="Receipts" className="rounded-lg border border-border bg-card">
        <Suspense fallback={<Skeleton className="h-72 rounded-lg" />}>
          <SalesList searchParams={searchParams} />
        </Suspense>
      </section>
    </div>
  );
}

async function Header() {
  const me = await getCurrentUser();
  return (
    <PageHeader
      title="Sales history"
      description={
        canManageInventory(me.role)
          ? "Every receipt, newest first. Open one to see it or give a refund."
          : "Your receipts, newest first. Refunds are given by an owner or manager."
      }
    />
  );
}

async function SalesList({ searchParams }: { searchParams: PageProps<"/sales">["searchParams"] }) {
  const me = await getCurrentUser();
  const raw = await searchParams;
  const typed = first(raw.receipt)?.trim() ?? "";
  const receipt = normalizeReceiptQuery(typed);
  const page = Math.max(1, Number.parseInt(first(raw.page) ?? "1", 10) || 1);

  const searchForm = (
    <form role="search" action="/sales" className="flex flex-wrap items-end gap-2 border-b border-border px-4 py-3 sm:px-5">
      <div className="grid min-w-48 flex-1 gap-1.5 sm:max-w-xs">
        <label htmlFor="receipt-search" className="text-[0.8125rem] font-medium">
          Find a receipt
        </label>
        <Input
          id="receipt-search"
          name="receipt"
          defaultValue={typed}
          placeholder="S-000123 or 123"
          inputMode="search"
          autoComplete="off"
          aria-invalid={receipt === null}
          aria-describedby={receipt === null ? "receipt-search-error" : undefined}
        />
      </div>
      <Button type="submit" variant="outline">
        <Search aria-hidden="true" />
        Search
      </Button>
      {typed && (
        <Button variant="ghost" asChild>
          <Link href="/sales">Show all</Link>
        </Button>
      )}
      {receipt === null && (
        <p id="receipt-search-error" role="alert" className="basis-full text-sm text-destructive">
          Enter a receipt number like S-000123 or 123.
        </p>
      )}
    </form>
  );
  if (receipt === null) return searchForm;

  let result;
  try {
    result = await listSales({ receipt, page });
  } catch (error) {
    if (error instanceof ApiUnavailableError) {
      return <ApiErrorState retryHref="/sales" title="Can't load sales" />;
    }
    throw error;
  }

  return (
    <>
      {searchForm}
      {result.items.length > 0 ? (
        <>
          <SalesTable sales={result.items} showCashier={canManageInventory(me.role)} timeZone={me.organization.timezone} />
          <div className="border-t border-border">
            <Pagination
              page={page}
              pageSize={SALES_PAGE_SIZE}
              total={result.total}
              searchParams={typed ? { receipt: typed } : {}}
              basePath="/sales"
            />
          </div>
        </>
      ) : (
        <div className="grid place-items-center px-6 py-14 text-center">
          <ReceiptText className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 font-display text-xl font-semibold">{typed ? `No receipt ${typed}` : "No sales yet"}</h2>
          <p className="mt-1.5 max-w-md text-muted-foreground">
            {typed
              ? "Check the number on the printed receipt. Cashiers can only find their own receipts."
              : "Receipts appear here as soon as a sale is recorded."}
          </p>
          <Button className="mt-5" variant={typed ? "outline" : "default"} asChild>
            {typed ? <Link href="/sales">Show all receipts</Link> : <Link href="/sell">Make a sale</Link>}
          </Button>
        </div>
      )}
    </>
  );
}

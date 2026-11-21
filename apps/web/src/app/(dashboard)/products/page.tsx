import { PackagePlus, Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { Pagination } from "@/components/products/pagination";
import { ProductFilters } from "@/components/products/product-filters";
import { ProductsTable } from "@/components/products/products-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { listCategories, listProducts, PRODUCTS_PAGE_SIZE } from "@/lib/api/products";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { isProductSort, isStockStatus } from "@/lib/products";

export const metadata: Metadata = {
  title: "Products",
};

/** The page itself is static; the product list streams in behind Suspense (Cache Components). */
export default function ProductsPage({ searchParams }: PageProps<"/products">) {
  return (
    <div className="grid gap-5">
      <PageHeader
        title="Products"
        description="Everything you sell, with prices and stock on hand."
        action={
          <Suspense fallback={null}>
            <AddProductButton />
          </Suspense>
        }
      />
      <section aria-label="Product list" className="rounded-lg border border-border bg-card">
        <Suspense fallback={<ProductsSkeleton />}>
          <ProductsResults searchParams={searchParams} />
        </Suspense>
      </section>
    </div>
  );
}

/** Only owners and managers see "Add product"; the role is request-time data, hence Suspense. */
async function AddProductButton() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) return null;
  return (
    <Button size="lg" asChild>
      <Link href="/products/new">
        <Plus aria-hidden="true" />
        Add product
      </Link>
    </Button>
  );
}

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

async function ProductsResults({ searchParams }: { searchParams: PageProps<"/products">["searchParams"] }) {
  const raw = await searchParams;
  const q = first(raw.q)?.slice(0, 100) || undefined;
  const statusParam = first(raw.status);
  const status = isStockStatus(statusParam) ? statusParam : undefined;
  const sortParam = first(raw.sort);
  const sort = isProductSort(sortParam) ? sortParam : undefined;
  const categoryId = first(raw.category) || undefined;
  const page = Math.max(1, Number.parseInt(first(raw.page) ?? "1", 10) || 1);

  const kept: Record<string, string> = {};
  if (q) kept.q = q;
  if (status) kept.status = status;
  if (sort) kept.sort = sort;
  if (categoryId) kept.category = categoryId;
  const hasFilters = Boolean(q || status || categoryId);

  let result;
  let categories;
  let me;
  try {
    [result, categories, me] = await Promise.all([
      listProducts({ q, status, sort, categoryId, page }),
      listCategories(),
      getCurrentUser(),
    ]);
  } catch (error) {
    if (error instanceof ApiUnavailableError) {
      const query = new URLSearchParams({ ...kept, ...(page > 1 && { page: String(page) }) }).toString();
      return <ApiErrorState retryHref={query ? `/products?${query}` : "/products"} />;
    }
    throw error;
  }

  return (
    <>
      <div className="border-b border-border p-4 sm:px-5">
        <ProductFilters categories={categories} />
      </div>
      {result.items.length > 0 ? (
        <>
          <ProductsTable products={result.items} />
          <div className="border-t border-border">
            <Pagination page={page} pageSize={PRODUCTS_PAGE_SIZE} total={result.total} searchParams={kept} />
          </div>
        </>
      ) : hasFilters ? (
        <div className="grid place-items-center px-6 py-14 text-center">
          <h2 className="font-display text-xl font-semibold">No products match these filters</h2>
          <p className="mt-1.5 text-muted-foreground">Try a different search, or clear the filters.</p>
          <Button variant="outline" className="mt-5" asChild>
            <Link href="/products">Clear filters</Link>
          </Button>
        </div>
      ) : (
        <div className="grid place-items-center px-6 py-14 text-center">
          <PackagePlus className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 font-display text-xl font-semibold">Add your first product</h2>
          <p className="mt-1.5 max-w-md text-muted-foreground">
            Products hold the price and stock of everything you sell. Start with your best sellers.
          </p>
          {canManageInventory(me.role) ? (
            <Button className="mt-5" asChild>
              <Link href="/products/new">Add product</Link>
            </Button>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">Ask your store owner or manager to add products.</p>
          )}
        </div>
      )}
    </>
  );
}

function ProductsSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading products">
      <div className="flex flex-wrap gap-3 border-b border-border p-4 sm:px-5">
        <Skeleton className="h-9 min-w-56 flex-1" />
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-9 w-40" />
      </div>
      <div className="grid gap-3 p-4 sm:px-5">
        {Array.from({ length: 8 }, (_, index) => (
          <Skeleton key={index} className="h-9 w-full" />
        ))}
      </div>
    </div>
  );
}

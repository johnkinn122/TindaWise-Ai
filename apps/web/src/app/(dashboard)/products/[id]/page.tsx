import { ChevronLeft, Pencil } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { Panel } from "@/components/dashboard/panel";
import { StockBadge } from "@/components/dashboard/stock-badge";
import { RoleNotice } from "@/components/auth/role-notice";
import { ApiErrorState } from "@/components/products/api-error-state";
import { ArchiveProductButton } from "@/components/products/archive-product-button";
import { MovementHistory } from "@/components/products/movement-history";
import { StockAdjustForm } from "@/components/products/stock-adjust-form";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getProduct, listMovements } from "@/lib/api/products";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import type { Product } from "@/lib/api/types";
import { formatNumber, formatPeso, formatPercent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Product",
};

export default function ProductPage({ params }: PageProps<"/products/[id]">) {
  return (
    <div className="grid gap-5">
      <Link
        href="/products"
        className="inline-flex w-fit items-center gap-1 text-[0.8125rem] font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        All products
      </Link>
      <Suspense fallback={<ProductSkeleton />}>
        <ProductDetail params={params} />
      </Suspense>
    </div>
  );
}

async function ProductDetail({ params }: { params: PageProps<"/products/[id]">["params"] }) {
  const { id } = await params;
  let product: Product;
  let movements;
  let me;
  try {
    [product, movements, me] = await Promise.all([getProduct(id), listMovements(id), getCurrentUser()]);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref={`/products/${id}`} />;
    throw error;
  }
  const canManage = canManageInventory(me.role);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-display font-bold">{product.name}</h1>
          <p className="mt-1 text-[0.8125rem] text-muted-foreground">
            SKU {product.sku}
            {product.barcode && <> · Barcode {product.barcode}</>}
            {!product.is_active && <span className="ml-2 font-medium text-warning">Archived</span>}
          </p>
        </div>
        {product.is_active && canManage && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link href={`/products/${product.id}/edit`}>
                <Pencil aria-hidden="true" />
                Edit
              </Link>
            </Button>
            <ArchiveProductButton productId={product.id} productName={product.name} />
          </div>
        )}
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="grid min-w-0 gap-5 lg:col-span-7">
          <Panel title="Stock">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-4 sm:px-5">
              <p>
                <span className="tabular font-display text-kpi font-semibold">
                  {formatNumber(product.stock_on_hand)}
                </span>
                <span className="ml-1.5 text-muted-foreground">{product.unit} on hand</span>
              </p>
              <StockBadge status={product.stock_status} />
              <p className="text-[0.8125rem] text-muted-foreground">
                Reorder at {formatNumber(product.reorder_level)}
              </p>
            </div>
            <div className="border-t border-border px-4 py-4 sm:px-5">
              <h3 className="mb-3 font-semibold">Adjust stock</h3>
              {canManage ? (
                <StockAdjustForm product={product} />
              ) : (
                <RoleNotice>Only owners and managers can change stock. Sales will update it automatically.</RoleNotice>
              )}
            </div>
          </Panel>

          <Panel title="Stock history">
            <MovementHistory movements={movements.items} />
            {movements.total > movements.items.length && (
              <p className="border-t border-border px-4 py-3 text-[0.8125rem] text-muted-foreground sm:px-5">
                Showing the latest {movements.items.length} of {formatNumber(movements.total)} changes.
              </p>
            )}
          </Panel>
        </div>

        <div className="min-w-0 lg:col-span-5">
          <Panel title="Details">
            <ProductFacts product={product} />
          </Panel>
        </div>
      </div>
    </>
  );
}

/**
 * Margin per unit = price − cost; margin % = (price − cost) ÷ price. Computed in centavos to stay exact.
 * Cashiers get no cost from the API, so they see neither cost nor margin.
 */
function ProductFacts({ product }: { product: Product }) {
  const priceCents = Math.round(Number(product.price) * 100);
  const costFacts: [string, string][] = [];
  if (product.cost !== null) {
    const costCents = Math.round(Number(product.cost) * 100);
    const marginCents = priceCents - costCents;
    costFacts.push(
      ["Cost", formatPeso(costCents / 100)],
      [
        "Margin per unit",
        priceCents > 0 ? `${formatPeso(marginCents / 100)} (${formatPercent(marginCents / priceCents)})` : "—",
      ],
    );
  }
  const facts: [string, string][] = [
    ["Selling price", formatPeso(priceCents / 100)],
    ...costFacts,
    ["Category", product.category?.name ?? "—"],
    ["Unit", product.unit],
    ["Barcode", product.barcode ?? "—"],
  ];
  return (
    <dl className="divide-y divide-border">
      {facts.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-4 px-4 py-3 sm:px-5">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="tabular text-right font-medium">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function ProductSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading product" className="grid gap-5">
      <Skeleton className="h-10 w-80 max-w-full" />
      <div className="grid gap-5 lg:grid-cols-12">
        <Skeleton className="h-96 lg:col-span-7" />
        <Skeleton className="h-72 lg:col-span-5" />
      </div>
    </div>
  );
}

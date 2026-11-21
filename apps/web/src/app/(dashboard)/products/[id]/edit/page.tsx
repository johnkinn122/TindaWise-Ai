import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PageHeader } from "@/components/dashboard/page-header";
import { RoleNotice } from "@/components/auth/role-notice";
import { ApiErrorState } from "@/components/products/api-error-state";
import { ProductForm } from "@/components/products/product-form";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getProduct, listCategories } from "@/lib/api/products";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { updateProductAction } from "../../actions";

export const metadata: Metadata = {
  title: "Edit product",
};

export default function EditProductPage({ params }: PageProps<"/products/[id]/edit">) {
  return (
    <div className="grid max-w-3xl gap-5">
      <PageHeader title="Edit product" />
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <EditProductForm params={params} />
        </Suspense>
      </div>
    </div>
  );
}

async function EditProductForm({ params }: { params: PageProps<"/products/[id]/edit">["params"] }) {
  const { id } = await params;
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return <RoleNotice>Only owners and managers can edit products.</RoleNotice>;
  }
  let product;
  let categories;
  try {
    [product, categories] = await Promise.all([getProduct(id), listCategories()]);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref={`/products/${id}/edit`} />;
    throw error;
  }
  return (
    <ProductForm
      action={updateProductAction.bind(null, product.id)}
      categories={categories}
      product={product}
      submitLabel="Save changes"
      cancelHref={`/products/${product.id}`}
    />
  );
}

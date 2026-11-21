import type { Metadata } from "next";
import { Suspense } from "react";
import { PageHeader } from "@/components/dashboard/page-header";
import { RoleNotice } from "@/components/auth/role-notice";
import { ApiErrorState } from "@/components/products/api-error-state";
import { ProductForm } from "@/components/products/product-form";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { listCategories } from "@/lib/api/products";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { createProductAction } from "../actions";

export const metadata: Metadata = {
  title: "Add product",
};

export default function NewProductPage() {
  return (
    <div className="grid max-w-3xl gap-5">
      <PageHeader title="Add product" />
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <NewProductForm />
        </Suspense>
      </div>
    </div>
  );
}

async function NewProductForm() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return <RoleNotice>Only owners and managers can add products.</RoleNotice>;
  }
  let categories;
  try {
    categories = await listCategories();
  } catch (error) {
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref="/products/new" />;
    throw error;
  }
  return (
    <ProductForm
      action={createProductAction}
      categories={categories}
      submitLabel="Add product"
      cancelHref="/products"
    />
  );
}

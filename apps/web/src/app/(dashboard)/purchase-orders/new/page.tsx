import type { Metadata } from "next";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { PurchaseOrderEditor } from "@/components/purchase-orders/purchase-order-editor";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { listSuppliers } from "@/lib/api/suppliers";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "New purchase order",
};

export default function NewPurchaseOrderPage() {
  return (
    <div className="grid max-w-4xl gap-5">
      <PageHeader title="New purchase order" description="Saved as a draft. The owner approves it before you order." />
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <NewOrder />
        </Suspense>
      </div>
    </div>
  );
}

async function NewOrder() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) return <RoleNotice>Only owners and managers can create purchase orders.</RoleNotice>;
  let suppliers;
  try {
    suppliers = await listSuppliers();
  } catch (error) {
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref="/purchase-orders/new" title="Can't load suppliers" />;
    throw error;
  }
  return <PurchaseOrderEditor suppliers={suppliers.items} />;
}

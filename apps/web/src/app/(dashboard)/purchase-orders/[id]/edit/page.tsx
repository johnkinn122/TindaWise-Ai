import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { PurchaseOrderEditor } from "@/components/purchase-orders/purchase-order-editor";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getPurchaseOrder } from "@/lib/api/purchase-orders";
import { listSuppliers } from "@/lib/api/suppliers";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "Edit purchase order",
};

export default function EditPurchaseOrderPage({ params }: PageProps<"/purchase-orders/[id]/edit">) {
  return (
    <div className="grid max-w-4xl gap-5">
      <Suspense fallback={<Skeleton className="h-[32rem] w-full" />}>
        <EditOrder params={params} />
      </Suspense>
    </div>
  );
}

async function EditOrder({ params }: { params: PageProps<"/purchase-orders/[id]/edit">["params"] }) {
  const { id } = await params;
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <>
        <PageHeader title="Edit purchase order" />
        <RoleNotice>Only owners and managers can edit purchase orders.</RoleNotice>
      </>
    );
  }
  let po;
  let suppliers;
  try {
    [po, suppliers] = await Promise.all([getPurchaseOrder(id), listSuppliers()]);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) {
      return <ApiErrorState retryHref={`/purchase-orders/${id}/edit`} title="Can't load the purchase order" />;
    }
    throw error;
  }
  if (po.status !== "draft") {
    return (
      <>
        <PageHeader title={`Edit ${po.code}`} />
        <RoleNotice>
          Only drafts can be edited. This order is no longer a draft.{" "}
          <Link href={`/purchase-orders/${po.id}`} className="font-medium text-foreground underline underline-offset-4">
            Open {po.code}
          </Link>
        </RoleNotice>
      </>
    );
  }
  return (
    <>
      <PageHeader title={`Edit ${po.code}`} description="Draft. Review the products and quantities, and choose a supplier." />
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <PurchaseOrderEditor po={po} suppliers={suppliers.items} />
      </div>
    </>
  );
}

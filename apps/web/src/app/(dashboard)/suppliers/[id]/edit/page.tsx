import { Archive } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ConfirmActionButton } from "@/components/forms/confirm-action-button";
import { ApiErrorState } from "@/components/products/api-error-state";
import { SupplierForm } from "@/components/suppliers/supplier-form";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getSupplier } from "@/lib/api/suppliers";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { archiveSupplierAction, updateSupplierAction } from "../../actions";

export const metadata: Metadata = {
  title: "Edit supplier",
};

export default function EditSupplierPage({ params }: PageProps<"/suppliers/[id]/edit">) {
  return (
    <div className="grid max-w-3xl gap-5">
      <Suspense fallback={<Skeleton className="h-[32rem] w-full" />}>
        <EditSupplier params={params} />
      </Suspense>
    </div>
  );
}

async function EditSupplier({ params }: { params: PageProps<"/suppliers/[id]/edit">["params"] }) {
  const { id } = await params;
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <>
        <PageHeader title="Edit supplier" />
        <RoleNotice>Only owners and managers can edit suppliers.</RoleNotice>
      </>
    );
  }
  let supplier;
  try {
    supplier = await getSupplier(id);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref={`/suppliers/${id}/edit`} title="Can't load supplier" />;
    throw error;
  }
  return (
    <>
      <PageHeader
        title={supplier.name}
        description={supplier.is_active ? "Edit contact details." : "Archived supplier."}
        action={
          supplier.is_active ? (
            <ConfirmActionButton
              triggerVariant="destructive"
              trigger={
                <>
                  <Archive aria-hidden="true" />
                  Archive
                </>
              }
              title={`Archive ${supplier.name}?`}
              description="It disappears from your supplier list and can't be picked for new orders. Its purchase orders are kept."
              confirmLabel="Archive supplier"
              pendingLabel="Archiving…"
              cancelLabel="Keep supplier"
              destructive
              action={archiveSupplierAction.bind(null, supplier.id)}
            />
          ) : undefined
        }
      />
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <SupplierForm action={updateSupplierAction.bind(null, supplier.id)} supplier={supplier} submitLabel="Save changes" />
      </div>
    </>
  );
}

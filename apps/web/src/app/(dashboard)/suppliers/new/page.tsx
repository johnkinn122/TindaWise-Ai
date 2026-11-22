import type { Metadata } from "next";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { SupplierForm } from "@/components/suppliers/supplier-form";
import { Skeleton } from "@/components/ui/skeleton";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { createSupplierAction } from "../actions";

export const metadata: Metadata = {
  title: "Add supplier",
};

export default function NewSupplierPage() {
  return (
    <div className="grid max-w-3xl gap-5">
      <PageHeader title="Add supplier" />
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <NewSupplierForm />
        </Suspense>
      </div>
    </div>
  );
}

async function NewSupplierForm() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) return <RoleNotice>Only owners and managers can add suppliers.</RoleNotice>;
  return <SupplierForm action={createSupplierAction} submitLabel="Add supplier" />;
}

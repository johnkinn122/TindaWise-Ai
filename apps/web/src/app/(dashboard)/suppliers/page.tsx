import { Plus, Truck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { SuppliersTable } from "@/components/suppliers/suppliers-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError } from "@/lib/api/client";
import { listSuppliers } from "@/lib/api/suppliers";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "Suppliers",
};

export default function SuppliersPage() {
  return (
    <div className="grid gap-5">
      <PageHeader
        title="Suppliers"
        description="Who you buy from, and how to reach them."
        action={
          <Suspense fallback={null}>
            <HeaderActions />
          </Suspense>
        }
      />
      <section aria-label="Supplier list" className="rounded-lg border border-border bg-card">
        <Suspense fallback={<Skeleton className="h-64 rounded-lg" />}>
          <SupplierList />
        </Suspense>
      </section>
    </div>
  );
}

async function HeaderActions() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) return null;
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" size="lg" asChild>
        <Link href="/purchase-orders">Purchase orders</Link>
      </Button>
      <Button size="lg" asChild>
        <Link href="/suppliers/new">
          <Plus aria-hidden="true" />
          Add supplier
        </Link>
      </Button>
    </div>
  );
}

async function SupplierList() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <div className="p-4 sm:p-5">
        <RoleNotice>Only owners and managers can see suppliers and purchase orders.</RoleNotice>
      </div>
    );
  }
  let result;
  try {
    result = await listSuppliers();
  } catch (error) {
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref="/suppliers" title="Can't load suppliers" />;
    throw error;
  }
  if (result.items.length === 0) {
    return (
      <div className="grid place-items-center px-6 py-14 text-center">
        <Truck className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
        <h2 className="mt-4 font-display text-xl font-semibold">Add your first supplier</h2>
        <p className="mt-1.5 max-w-md text-muted-foreground">
          Suppliers are who you order from. Purchase orders need one before the owner can approve them.
        </p>
        <Button className="mt-5" asChild>
          <Link href="/suppliers/new">Add supplier</Link>
        </Button>
      </div>
    );
  }
  return <SuppliersTable suppliers={result.items} />;
}

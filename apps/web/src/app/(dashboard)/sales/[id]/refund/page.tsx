import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { RefundForm } from "@/components/sales/refund-form";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getSale } from "@/lib/api/sales";
import type { Sale } from "@/lib/api/types";
import { canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { formatDateTime } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";
import { canRefund, paymentMethodLabels } from "@/lib/sales";

export const metadata: Metadata = {
  title: "Refund",
};

export default function RefundPage({ params }: PageProps<"/sales/[id]/refund">) {
  return (
    <div className="mx-auto grid w-full max-w-3xl gap-5">
      <Suspense fallback={<Skeleton className="h-96" aria-busy="true" aria-label="Loading refund" />}>
        <Refund params={params} />
      </Suspense>
    </div>
  );
}

async function Refund({ params }: { params: PageProps<"/sales/[id]/refund">["params"] }) {
  const { id } = await params;
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <>
        <PageHeader title="Refund" />
        <RoleNotice>Only owners and managers can give refunds.</RoleNotice>
      </>
    );
  }

  let sale: Sale;
  try {
    sale = await getSale(id);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) {
      return <ApiErrorState retryHref={`/sales/${id}/refund`} title="Can't load the receipt" />;
    }
    throw error;
  }

  const header = (
    <PageHeader
      title={`Refund on ${sale.receipt_code}`}
      description={`${formatDateTime(sale.created_at)} · ${formatCents(toCents(sale.total))} paid by ${paymentMethodLabels[sale.payment_method].toLowerCase()}${sale.cashier_name ? ` · ${sale.cashier_name}` : ""}`}
    />
  );

  if (!canRefund(sale, true)) {
    return (
      <>
        {header}
        <RoleNotice>Everything on this receipt has already been refunded.</RoleNotice>
        <Button variant="outline" className="justify-self-start" asChild>
          <Link href={`/sales/${sale.id}`}>Back to the receipt</Link>
        </Button>
      </>
    );
  }

  return (
    <>
      {header}
      <RefundForm sale={sale} />
    </>
  );
}

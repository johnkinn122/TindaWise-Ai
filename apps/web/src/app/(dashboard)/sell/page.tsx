import type { Metadata } from "next";
import { Suspense } from "react";
import { PageHeader } from "@/components/dashboard/page-header";
import { PosTerminal } from "@/components/pos/pos-terminal";
import { Skeleton } from "@/components/ui/skeleton";
import { getCurrentUser } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "Sell",
};

export default function SellPage() {
  return (
    <div className="grid gap-5">
      <PageHeader title="Sell" description="Scan items, take payment, print the receipt." />
      <Suspense fallback={<SellSkeleton />}>
        <SellScreen />
      </Suspense>
    </div>
  );
}

/** Every role can sell, so the only things read here are the store's name and time zone for the receipt. */
async function SellScreen() {
  const me = await getCurrentUser();
  return <PosTerminal storeName={me.organization.name} timeZone={me.organization.timezone} />;
}

function SellSkeleton() {
  return (
    <div className="grid gap-5 lg:grid-cols-12" aria-busy="true" aria-label="Loading checkout">
      <Skeleton className="h-48 lg:col-span-7" />
      <Skeleton className="h-96 lg:col-span-5" />
    </div>
  );
}

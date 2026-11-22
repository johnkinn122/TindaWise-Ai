import type { Metadata } from "next";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ApiErrorState } from "@/components/products/api-error-state";
import { StoreForm } from "@/components/settings/store-form";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiUnavailableError, apiFetch } from "@/lib/api/client";
import type { Store } from "@/lib/api/types";
import { canEditStore, canManageInventory, getCurrentUser } from "@/lib/auth/current-user";
import { timeZoneOptions, utcOffset } from "@/lib/time-zones";

export const metadata: Metadata = {
  title: "Store settings",
};

export default function StoreSettingsPage() {
  return (
    <div className="grid max-w-3xl gap-5">
      <PageHeader title="Store settings" description="Your store's name, time zone and reorder defaults." />
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <StoreSettings />
      </Suspense>
    </div>
  );
}

async function StoreSettings() {
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return <RoleNotice>Only the store owner and managers can see store settings.</RoleNotice>;
  }

  let store: Store;
  try {
    store = await apiFetch<Store>("/store");
  } catch (error) {
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref="/settings/store" />;
    throw error;
  }

  if (!canEditStore(me.role)) {
    return (
      <>
        <RoleNotice>Only the store owner can change these settings.</RoleNotice>
        <Panel title="Store">
          <StoreDetails store={store} />
        </Panel>
      </>
    );
  }

  return (
    <Panel title="Store">
      <div className="px-4 py-5 sm:px-5">
        <StoreForm store={store} timeZones={timeZoneOptions(store.timezone)} />
      </div>
    </Panel>
  );
}

function StoreDetails({ store }: { store: Store }) {
  const offset = utcOffset(store.timezone, new Date());
  const rows: [string, string][] = [
    ["Store name", store.name],
    ["Time zone", offset ? `${store.timezone.replaceAll("_", " ")} (${offset})` : store.timezone],
    [
      "Default delivery time",
      `${store.default_lead_time_days} ${store.default_lead_time_days === 1 ? "day" : "days"}`,
    ],
    ["Currency", store.currency],
  ];
  return (
    <dl className="divide-y divide-border text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-[14rem_1fr] sm:px-5">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

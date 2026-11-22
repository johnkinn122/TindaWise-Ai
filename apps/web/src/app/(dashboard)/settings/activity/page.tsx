import { History } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { ApiErrorState } from "@/components/products/api-error-state";
import { Pagination } from "@/components/products/pagination";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  ACTIVITY_PAGE_SIZE,
  type ActivityParams,
  actionLabels,
  activityLink,
  activityQuery,
  parseActivityParams,
} from "@/lib/activity";
import { ApiUnavailableError, apiFetch } from "@/lib/api/client";
import type { AuditEvent, Page } from "@/lib/api/types";
import { canEditStore, getCurrentUser } from "@/lib/auth/current-user";
import { formatDateTime } from "@/lib/format";

export const metadata: Metadata = {
  title: "Activity log",
};

export default function ActivityPage({ searchParams }: PageProps<"/settings/activity">) {
  return (
    <div className="grid max-w-5xl gap-5">
      <PageHeader
        title="Activity log"
        description="Sensitive changes in your store: who made them and when. Entries can't be edited or deleted."
      />
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <Activity searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Activity({ searchParams }: { searchParams: PageProps<"/settings/activity">["searchParams"] }) {
  const me = await getCurrentUser();
  if (!canEditStore(me.role)) {
    return <RoleNotice>Only the store owner can see the activity log.</RoleNotice>;
  }
  const params = parseActivityParams(await searchParams);

  let page: Page<AuditEvent>;
  try {
    page = await apiFetch<Page<AuditEvent>>("/audit-events", { query: activityQuery(params) });
  } catch (error) {
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref="/settings/activity" />;
    throw error;
  }

  return (
    // min-w-0: a grid item is as wide as its content by default, so the table would widen the page.
    <section aria-label="Activity" className="min-w-0 rounded-lg border border-border bg-card">
      <ActionFilter params={params} />
      {page.items.length > 0 ? (
        <>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4 sm:pl-5">When</TableHead>
                <TableHead>What</TableHead>
                <TableHead className="hidden pr-4 md:table-cell md:pr-5">Who</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((event) => {
                const link = activityLink(event);
                return (
                  <TableRow key={event.id}>
                    <TableCell className="w-24 whitespace-normal pl-4 align-top tabular text-muted-foreground sm:w-auto sm:whitespace-nowrap sm:pl-5">
                      {formatDateTime(event.created_at, me.organization.timezone)}
                    </TableCell>
                    <TableCell className="whitespace-normal align-top">
                      <div className="text-xs text-muted-foreground">{actionLabels[event.action] ?? event.action}</div>
                      <div>{event.summary}</div>
                      {/* Phones: who did it goes under the summary. */}
                      <div className="text-xs text-muted-foreground md:hidden">{event.actor_name ?? "System"}</div>
                      {link && (
                        <Link
                          href={link.href}
                          className="text-xs font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {link.label}
                        </Link>
                      )}
                    </TableCell>
                    <TableCell className="hidden pr-4 align-top md:table-cell md:pr-5">
                      {event.actor_name ?? "System"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <div className="border-t border-border">
            <Pagination
              page={params.page}
              pageSize={ACTIVITY_PAGE_SIZE}
              total={page.total}
              searchParams={params.action ? { action: params.action } : {}}
              basePath="/settings/activity"
            />
          </div>
        </>
      ) : (
        <div className="grid place-items-center px-6 py-14 text-center">
          <History className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
          <h2 className="mt-4 font-display text-xl font-semibold">
            {params.action ? "Nothing of this kind yet" : "No activity yet"}
          </h2>
          <p className="mt-1.5 max-w-md text-muted-foreground">
            Refunds, purchase order approvals, price changes, archived products, new team members and store settings
            changes appear here.
          </p>
          {params.action && (
            <Button className="mt-5" variant="outline" asChild>
              <Link href="/settings/activity">Show all activity</Link>
            </Button>
          )}
        </div>
      )}
    </section>
  );
}

function ActionFilter({ params }: { params: ActivityParams }) {
  return (
    <form method="get" className="flex flex-wrap items-end gap-2 border-b border-border px-4 py-3 sm:px-5">
      <div className="grid gap-1.5">
        <label htmlFor="activity-action" className="text-sm font-medium">
          Show
        </label>
        <select
          id="activity-action"
          name="action"
          defaultValue={params.action ?? ""}
          className="h-9 rounded-sm border border-input bg-card px-2.5 text-sm"
        >
          <option value="">All activity</option>
          {Object.entries(actionLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" variant="outline">
        Apply
      </Button>
    </form>
  );
}

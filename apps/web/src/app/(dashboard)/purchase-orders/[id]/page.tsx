import { Ban, CircleCheck, PackageMinus, Pencil } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ConfirmActionButton } from "@/components/forms/confirm-action-button";
import { ApiErrorState } from "@/components/products/api-error-state";
import { ReceiveForm } from "@/components/purchase-orders/receive-form";
import { PurchaseOrderStatusBadge } from "@/components/purchase-orders/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getPurchaseOrder } from "@/lib/api/purchase-orders";
import type { PurchaseOrder } from "@/lib/api/types";
import { canManageInventory, getCurrentUser, type Role } from "@/lib/auth/current-user";
import { formatCalendarDate, formatDateTime, formatNumber } from "@/lib/format";
import { formatCents, toCents } from "@/lib/money";
import { approvalBlocker, availableActions } from "@/lib/purchase-orders";
import { approveAction, cancelAction, closeShortAction } from "../actions";

export const metadata: Metadata = {
  title: "Purchase order",
};

export default function PurchaseOrderPage({ params }: PageProps<"/purchase-orders/[id]">) {
  return (
    <div className="grid gap-5">
      <Suspense fallback={<OrderSkeleton />}>
        <Order params={params} />
      </Suspense>
    </div>
  );
}

const peso = (amount: string) => formatCents(toCents(amount));

const historyLabels: Record<PurchaseOrder["history"][number]["action"], string> = {
  created: "Drafted",
  approved: "Approved",
  received: "Delivery recorded",
  closed: "Closed short",
  cancelled: "Cancelled",
};

async function Order({ params }: { params: PageProps<"/purchase-orders/[id]">["params"] }) {
  const { id } = await params;
  const me = await getCurrentUser();
  if (!canManageInventory(me.role)) {
    return (
      <>
        <PageHeader title="Purchase order" />
        <RoleNotice>Only owners and managers can see purchase orders.</RoleNotice>
      </>
    );
  }
  let po: PurchaseOrder;
  try {
    po = await getPurchaseOrder(id);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    if (error instanceof ApiUnavailableError) {
      return <ApiErrorState retryHref={`/purchase-orders/${id}`} title="Can't load the purchase order" />;
    }
    throw error;
  }

  const actions = availableActions(po, me.role);
  const blocker = approvalBlocker(po);

  return (
    <>
      <PageHeader
        title={po.code}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            <PurchaseOrderStatusBadge status={po.status} />
            {po.supplier ? po.supplier.name : "No supplier yet"}
          </span>
        }
        action={<OrderActions po={po} role={me.role} blocked={Boolean(blocker)} />}
      />

      {po.status === "draft" && (
        <RoleNotice>
          {blocker ??
            (actions.approve
              ? "Check the order, then approve it. Lines can't change after approval."
              : "Waiting for the owner's approval. Lines can't change after approval.")}
        </RoleNotice>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="grid min-w-0 gap-5 lg:col-span-8">
          <Panel title="Products">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-4 sm:pl-5">Product</TableHead>
                  <TableHead className="text-right">Ordered</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">Received</TableHead>
                  <TableHead className="hidden text-right md:table-cell">Unit cost</TableHead>
                  <TableHead className="pr-4 text-right sm:pr-5">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="whitespace-normal pl-4 sm:pl-5">
                      <Link href={`/products/${line.product_id}`} className="font-medium hover:underline">
                        {line.product_name}
                      </Link>
                      <div className="text-xs text-muted-foreground">{line.sku}</div>
                      <div className="tabular text-xs text-muted-foreground sm:hidden">
                        {formatNumber(line.quantity_received)} received
                      </div>
                    </TableCell>
                    <TableCell className="tabular text-right">
                      {formatNumber(line.quantity_ordered)}
                      <span className="ml-1 text-xs text-muted-foreground">{line.unit}</span>
                    </TableCell>
                    <TableCell className="tabular hidden text-right sm:table-cell">
                      {formatNumber(line.quantity_received)}
                    </TableCell>
                    <TableCell className="tabular hidden text-right md:table-cell">{peso(line.unit_cost)}</TableCell>
                    <TableCell className="tabular pr-4 text-right sm:pr-5">{peso(line.line_total)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={2} className="pl-4 font-semibold sm:pl-5">
                    Total
                  </TableCell>
                  <TableCell className="hidden sm:table-cell" />
                  <TableCell className="hidden md:table-cell" />
                  <TableCell className="tabular pr-4 text-right font-semibold sm:pr-5">{peso(po.total)}</TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </Panel>

          {actions.receive && (
            <Panel title="Record a delivery">
              <ReceiveForm po={po} />
            </Panel>
          )}

          {po.receipts.length > 0 && (
            <Panel title="Deliveries">
              <ol className="divide-y divide-border">
                {po.receipts.map((receipt) => (
                  <li key={receipt.id} className="px-4 py-3 text-sm sm:px-5">
                    <p className="font-medium">
                      {formatDateTime(receipt.created_at, me.organization.timezone)}
                      {receipt.received_by && <span className="font-normal text-muted-foreground"> · {receipt.received_by}</span>}
                    </p>
                    <ul className="mt-1 text-muted-foreground">
                      {receipt.lines.map((line) => (
                        <li key={line.product_id} className="tabular">
                          {formatNumber(line.quantity)} × {line.product_name}
                        </li>
                      ))}
                    </ul>
                    {receipt.note && <p className="mt-1 text-xs text-muted-foreground">Note: {receipt.note}</p>}
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </div>

        <div className="grid min-w-0 gap-5 lg:col-span-4">
          <Panel title="Details">
            <dl className="divide-y divide-border text-sm">
              <Fact label="Supplier" value={po.supplier?.name ?? "Not chosen yet"} />
              <Fact label="Expected" value={po.expected_on ? formatCalendarDate(po.expected_on) : "—"} />
              <Fact label="Products" value={formatNumber(po.line_count)} />
              {po.notes && <Fact label="Notes" value={po.notes} />}
            </dl>
          </Panel>
          <Panel title="History">
            <ol className="grid gap-3 px-4 py-3.5 text-sm sm:px-5">
              {po.history.map((event, index) => (
                <li key={`${event.action}-${index}`}>
                  <p className="font-medium">{historyLabels[event.action]}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDateTime(event.at, me.organization.timezone)}
                    {event.by && ` · ${event.by}`}
                  </p>
                </li>
              ))}
            </ol>
          </Panel>
        </div>
      </div>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 px-4 py-3 sm:px-5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

function OrderActions({ po, role, blocked }: { po: PurchaseOrder; role: Role; blocked: boolean }) {
  const actions = availableActions(po, role);
  if (!actions.edit && !actions.approve && !actions.cancel && !actions.closeShort) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {actions.cancel && (
        <ConfirmActionButton
          triggerVariant="destructive"
          trigger={
            <>
              <Ban aria-hidden="true" />
              Cancel order
            </>
          }
          title={`Cancel ${po.code}?`}
          description="Nothing has been received on it. It stays in your records as cancelled."
          confirmLabel="Cancel order"
          pendingLabel="Cancelling…"
          cancelLabel="Keep order"
          destructive
          action={cancelAction.bind(null, po.id)}
        />
      )}
      {actions.closeShort && (
        <ConfirmActionButton
          trigger={
            <>
              <PackageMinus aria-hidden="true" />
              Close short
            </>
          }
          title={`Close ${po.code} short?`}
          description="Use this when the rest won't arrive. What was delivered stays in stock; nothing more can be received on this order."
          confirmLabel="Close order"
          pendingLabel="Closing…"
          action={closeShortAction.bind(null, po.id)}
        />
      )}
      {actions.edit && (
        <Button variant="outline" asChild>
          <Link href={`/purchase-orders/${po.id}/edit`}>
            <Pencil aria-hidden="true" />
            Edit
          </Link>
        </Button>
      )}
      {actions.approve && !blocked && (
        <ConfirmActionButton
          triggerVariant="default"
          trigger={
            <>
              <CircleCheck aria-hidden="true" />
              Approve
            </>
          }
          title={`Approve ${po.code} for ${peso(po.total)}?`}
          description={`You agree to buy these ${po.line_count === 1 ? "product" : `${po.line_count} products`} from ${po.supplier?.name}. The lines can't be changed afterwards.`}
          confirmLabel="Approve order"
          pendingLabel="Approving…"
          action={approveAction.bind(null, po.id)}
        />
      )}
    </div>
  );
}

function OrderSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading purchase order" className="grid gap-5">
      <Skeleton className="h-12 w-72 max-w-full" />
      <div className="grid gap-5 lg:grid-cols-12">
        <Skeleton className="h-80 lg:col-span-8" />
        <Skeleton className="h-64 lg:col-span-4" />
      </div>
    </div>
  );
}

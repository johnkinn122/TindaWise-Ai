import { CircleCheck, FilePen, PackageCheck, PackageMinus, PackageOpen, X } from "lucide-react";
import type { PurchaseOrderStatus } from "@/lib/api/types";
import { statusLabels } from "@/lib/purchase-orders";
import { cn } from "@/lib/utils";

const styles: Record<PurchaseOrderStatus, { className: string; Icon: typeof X }> = {
  draft: { className: "text-muted-foreground", Icon: FilePen },
  approved: { className: "text-primary", Icon: CircleCheck },
  partially_received: { className: "text-warning", Icon: PackageOpen },
  received: { className: "text-success", Icon: PackageCheck },
  closed: { className: "text-muted-foreground", Icon: PackageMinus },
  cancelled: { className: "text-destructive", Icon: X },
};

/** Status with icon + text + color, never color alone (WCAG 1.4.1). Same shape as StockBadge. */
export function PurchaseOrderStatusBadge({ status }: { status: PurchaseOrderStatus }) {
  const { className, Icon } = styles[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-current px-2.5 py-0.5 text-xs font-medium",
        className,
      )}
    >
      <Icon className="size-3" strokeWidth={2.5} aria-hidden="true" />
      {statusLabels[status]}
    </span>
  );
}

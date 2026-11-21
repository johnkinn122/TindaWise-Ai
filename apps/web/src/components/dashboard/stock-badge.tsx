import { Circle, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StockStatus } from "@/lib/api/types";

const statusConfig: Record<StockStatus, { label: string; className: string; Icon: typeof Circle }> = {
  in_stock: { label: "In stock", className: "text-success", Icon: Circle },
  low_stock: { label: "Low stock", className: "text-warning", Icon: TriangleAlert },
  out_of_stock: { label: "Out of stock", className: "text-destructive", Icon: X },
};

/** Status is shown with icon + text + color, never color alone (WCAG 1.4.1). */
export function StockBadge({ status }: { status: StockStatus }) {
  const { label, className, Icon } = statusConfig[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-current px-2.5 py-0.5 text-xs font-medium",
        className,
      )}
    >
      <Icon
        className={cn("size-3", status === "in_stock" && "fill-current")}
        strokeWidth={2.5}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}

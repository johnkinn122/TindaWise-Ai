import { CircleCheck, RotateCcw, Undo2 } from "lucide-react";
import type { RefundStatus } from "@/lib/api/types";
import { refundStatusLabels } from "@/lib/sales";
import { cn } from "@/lib/utils";

const styles: Record<RefundStatus, { className: string; Icon: typeof Undo2 }> = {
  none: { className: "text-muted-foreground", Icon: CircleCheck },
  partial: { className: "text-warning", Icon: RotateCcw },
  full: { className: "text-destructive", Icon: Undo2 },
};

/** Icon + text + color, never color alone (WCAG 1.4.1). Same shape as the other status badges. */
export function RefundStatusBadge({ status }: { status: RefundStatus }) {
  const { className, Icon } = styles[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-current px-2.5 py-0.5 text-xs font-medium",
        className,
      )}
    >
      <Icon className="size-3" strokeWidth={2.5} aria-hidden="true" />
      {refundStatusLabels[status]}
    </span>
  );
}

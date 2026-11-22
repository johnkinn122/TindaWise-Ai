import { cn } from "@/lib/utils";
import type { Kpi } from "@/lib/overview";

const trendStyles: Record<Kpi["trend"], { className: string; symbol: string; srLabel: string }> = {
  up: { className: "text-success", symbol: "▲", srLabel: "Up" },
  down: { className: "text-destructive", symbol: "▼", srLabel: "Down" },
  neutral: { className: "text-muted-foreground", symbol: "", srLabel: "" },
};

/**
 * One panel split by dividers, read like a ledger row (MASTER.md §1),
 * rather than four separate cards. Wraps to 2×2 below 1024px.
 */
export function KpiStrip({ kpis }: { kpis: Kpi[] }) {
  return (
    <dl className="grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-card lg:grid-cols-4">
      {kpis.map((kpi, index) => {
        const trend = trendStyles[kpi.trend];
        return (
          <div
            key={kpi.id}
            className={cn(
              "px-4 py-4 sm:px-5",
              index % 2 === 1 && "border-l border-border",
              index >= 2 && "border-t border-border lg:border-t-0",
              index === 2 && "lg:border-l",
            )}
          >
            <dt className="text-[0.8125rem] text-muted-foreground">{kpi.label}</dt>
            <dd className="tabular mt-1.5 font-display text-kpi font-semibold">{kpi.value}</dd>
            <dd className={cn("mt-1 text-xs font-medium", trend.className)}>
              {trend.symbol && (
                <span aria-hidden="true" className="mr-1">
                  {trend.symbol}
                </span>
              )}
              {trend.srLabel && <span className="sr-only">{trend.srLabel} </span>}
              {kpi.change}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

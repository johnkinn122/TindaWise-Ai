import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ReportParams } from "@/lib/api/reports";
import type { ReportPeriod } from "@/lib/api/types";
import { reportPresets, reportQuery } from "@/lib/reports";
import { cn } from "@/lib/utils";

interface ReportFiltersProps {
  params: ReportParams;
  /** The period the API resolved, so the custom fields show real dates even for a preset. */
  period: ReportPeriod;
}

/**
 * One row above everything it scopes: presets first, then a custom range. Plain links and a GET
 * form, so every view has a URL (shareable, back button works) and nothing needs JavaScript.
 */
export function ReportFilters({ params, period }: ReportFiltersProps) {
  return (
    // min-w-0: a grid item may shrink below its content, so the preset bar scrolls instead of widening the page.
    <div className="flex min-w-0 flex-wrap items-end justify-between gap-3">
      <nav aria-label="Report period" className="flex max-w-full gap-1 overflow-x-auto rounded-sm border border-border bg-card p-1">
        {reportPresets.map((preset) => {
          const active = params.preset === preset.id;
          return (
            <Link
              key={preset.id}
              href={`/reports?${reportQuery(params, { preset: preset.id, start: undefined, end: undefined })}`}
              aria-current={active ? "page" : undefined}
              className={cn(
                "whitespace-nowrap rounded-[4px] px-3 py-1.5 text-sm font-medium",
                active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {preset.label}
            </Link>
          );
        })}
      </nav>
      <form action="/reports" method="get" className="flex flex-wrap items-end gap-2" aria-label="Custom period">
        {params.sort && params.sort !== "sales" && <input type="hidden" name="sort" value={params.sort} />}
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          From
          <Input type="date" name="start" defaultValue={period.start} required className="w-40 text-foreground" />
        </label>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          To
          <Input type="date" name="end" defaultValue={period.end} required className="w-40 text-foreground" />
        </label>
        <Button type="submit" variant={params.preset ? "outline" : "default"}>
          Show
        </Button>
      </form>
    </div>
  );
}

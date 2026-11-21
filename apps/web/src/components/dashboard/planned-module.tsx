import type { LucideIcon } from "lucide-react";
import { PageHeader } from "./page-header";

interface PlannedModuleProps {
  title: string;
  icon: LucideIcon;
  summary: string;
}

/**
 * Placeholder for modules on the roadmap that are not built yet.
 * Clearly marks them as planned (claude.md §2: distinguish planned from completed work).
 */
export function PlannedModule({ title, icon: Icon, summary }: PlannedModuleProps) {
  return (
    <div className="grid gap-5">
      <PageHeader title={title} />
      <div className="grid place-items-center rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
        <Icon className="size-8 text-muted-foreground" strokeWidth={1.5} aria-hidden="true" />
        <h2 className="mt-4 font-display text-xl font-semibold">{title} is planned</h2>
        <p className="mt-1.5 max-w-md text-muted-foreground">{summary}</p>
      </div>
    </div>
  );
}

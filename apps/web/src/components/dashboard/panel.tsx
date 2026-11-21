import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PanelProps {
  title: string;
  /** Used to link the heading to the section for screen readers. */
  id: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Bordered surface with a title row. Panels use a border, never a shadow (MASTER.md §4). */
export function Panel({ title, id, action, children, className }: PanelProps) {
  return (
    <section aria-labelledby={id} className={cn("rounded-lg border border-border bg-card", className)}>
      <div className="flex min-h-14 items-center justify-between gap-3 border-b border-border px-4 py-2.5 sm:px-5">
        <h2 id={id} className="text-lg font-semibold leading-snug">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

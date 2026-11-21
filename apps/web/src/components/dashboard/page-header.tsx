import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  /** The page's single primary action (MASTER.md §5). */
  action?: ReactNode;
}

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-display font-bold">{title}</h1>
        {description && <div className="mt-1 text-[0.8125rem] text-muted-foreground">{description}</div>}
      </div>
      {action}
    </div>
  );
}

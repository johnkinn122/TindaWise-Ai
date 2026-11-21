import { Search } from "lucide-react";
import { MobileNav } from "./mobile-nav";

interface TopBarProps {
  storeName: string;
}

export function TopBar({ storeName }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-card px-4 sm:px-6">
      <MobileNav />
      <span className="truncate font-medium">{storeName}</span>

      {/* Planned: global search (products, sales, suppliers). Disabled until the API exists. */}
      <div className="ml-auto w-full max-w-sm">
        <label htmlFor="global-search" className="sr-only">
          Search
        </label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <input
            id="global-search"
            type="search"
            disabled
            placeholder="Search — coming soon"
            className="h-9 w-full rounded-sm border border-input bg-background pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground disabled:cursor-not-allowed"
          />
        </div>
      </div>
    </header>
  );
}

import { Search } from "lucide-react";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { canManageInventory, canManageTeam, getCurrentUser, roleLabels } from "@/lib/auth/current-user";
import { MobileNav } from "./mobile-nav";
import { UserMenu } from "./user-menu";

/**
 * The bar itself is static (part of the prerendered shell). Only the store name and the account
 * menu depend on who is signed in, so only they wait behind Suspense.
 */
export function TopBar() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-card px-4 sm:px-6">
      <MobileNav />
      <Suspense fallback={<Skeleton className="h-5 w-40" />}>
        <StoreName />
      </Suspense>

      {/* Planned: global search (products, sales, suppliers). Disabled until it exists. */}
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

      <Suspense fallback={<Skeleton className="size-9 shrink-0 rounded-full" />}>
        <Account />
      </Suspense>
    </header>
  );
}

async function StoreName() {
  const me = await getCurrentUser();
  return <span className="truncate font-medium">{me.organization.name}</span>;
}

async function Account() {
  const me = await getCurrentUser();
  return (
    <UserMenu
      fullName={me.user.full_name}
      email={me.user.email}
      roleLabel={roleLabels[me.role]}
      canManageTeam={canManageTeam(me.role)}
      canViewStore={canManageInventory(me.role)}
    />
  );
}

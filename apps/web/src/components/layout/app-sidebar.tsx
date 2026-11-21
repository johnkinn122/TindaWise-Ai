import { BrandMark } from "./brand-mark";
import { NavLinks } from "./nav-links";
import { ThemeToggle } from "./theme-toggle";

/** Desktop sidebar (≥1024px). Below that, MobileNav renders the same links in a drawer. */
export function AppSidebar() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-3 py-4 lg:flex">
      <div className="px-2.5 pb-5 pt-1.5">
        <BrandMark />
      </div>
      <nav aria-label="Main">
        <NavLinks />
      </nav>
      <div className="mt-auto border-t border-sidebar-border pt-3">
        <ThemeToggle />
      </div>
    </aside>
  );
}

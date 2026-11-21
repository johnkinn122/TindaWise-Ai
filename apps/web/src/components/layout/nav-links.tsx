"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { cn } from "@/lib/utils";
import { navItems } from "./nav-items";

interface NavLinksProps {
  /** Called after a link is chosen — used to close the mobile drawer. */
  onNavigate?: () => void;
}

function isActive(href: string, pathname: string | null) {
  if (!pathname) return false;
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function NavLinkList({ pathname, onNavigate }: NavLinksProps & { pathname: string | null }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {navItems.map(({ href, label, icon: Icon }) => {
        const active = isActive(href, pathname);
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex h-10 items-center gap-3 rounded-sm px-3 font-medium text-muted-foreground transition-colors duration-150",
                "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                active &&
                  "bg-sidebar-accent text-sidebar-accent-foreground shadow-[inset_3px_0_0_var(--sidebar-primary)]",
              )}
            >
              <Icon className="size-[18px] shrink-0" strokeWidth={1.5} aria-hidden="true" />
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function ActiveNavLinks({ onNavigate }: NavLinksProps) {
  return <NavLinkList pathname={usePathname()} onNavigate={onNavigate} />;
}

/**
 * On routes with a dynamic segment (e.g. /products/[id]) the pathname isn't known while the
 * static shell is prerendered, so usePathname suspends. The fallback is the same list without
 * an active item; the highlight appears as soon as the request's pathname is known.
 */
export function NavLinks({ onNavigate }: NavLinksProps) {
  return (
    <Suspense fallback={<NavLinkList pathname={null} onNavigate={onNavigate} />}>
      <ActiveNavLinks onNavigate={onNavigate} />
    </Suspense>
  );
}

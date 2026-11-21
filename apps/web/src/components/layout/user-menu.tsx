"use client";

import { LogOut, Users } from "lucide-react";
import Link from "next/link";
import { logoutAction } from "@/app/(auth)/actions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface UserMenuProps {
  fullName: string;
  email: string;
  roleLabel: string;
  canManageTeam: boolean;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

export function UserMenu({ fullName, email, roleLabel, canManageTeam }: UserMenuProps) {
  const short = initials(fullName);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        // The accessible name starts with the visible initials (WCAG 2.5.3 Label in Name),
        // so voice-control users can say "click NS".
        aria-label={`${short}: Account, ${fullName}, ${roleLabel}`}
        className="grid size-9 shrink-0 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground outline-offset-2"
      >
        {short}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <div className="font-medium">{fullName}</div>
          <div className="truncate text-xs text-muted-foreground">{email}</div>
          <div className="mt-1 text-xs text-muted-foreground">{roleLabel}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {canManageTeam && (
          <DropdownMenuItem asChild>
            <Link href="/settings/team">
              <Users aria-hidden="true" />
              Team
            </Link>
          </DropdownMenuItem>
        )}
        {/* Sign out sits apart from everything else (MASTER.md §5: separate destructive actions). */}
        {canManageTeam && <DropdownMenuSeparator />}
        <DropdownMenuItem onSelect={() => void logoutAction()}>
          <LogOut aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

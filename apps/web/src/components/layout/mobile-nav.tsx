"use client";

import { Menu } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { BrandMark } from "./brand-mark";
import { NavLinks } from "./nav-links";
import { ThemeToggle } from "./theme-toggle";

/** Drawer navigation for screens below 1024px. */
export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon-lg" className="-ml-2 lg:hidden" aria-label="Open navigation">
          <Menu className="size-5" strokeWidth={1.5} aria-hidden="true" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 bg-sidebar px-3 py-4">
        <SheetTitle className="px-2.5 pt-1.5">
          <BrandMark />
        </SheetTitle>
        <SheetDescription className="sr-only">Main navigation</SheetDescription>
        <nav aria-label="Main">
          <NavLinks onNavigate={() => setOpen(false)} />
        </nav>
        <div className="mt-auto border-t border-sidebar-border pt-3">
          <ThemeToggle />
        </div>
      </SheetContent>
    </Sheet>
  );
}

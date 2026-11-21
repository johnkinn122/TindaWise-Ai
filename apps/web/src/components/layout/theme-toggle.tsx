"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "tindawise-theme";

/**
 * Inline script for <head>: applies the saved (or system) theme before first paint,
 * so dark-mode users never see a flash of the light theme.
 */
export const themeInitScript = `(function(){try{var t=localStorage.getItem("${STORAGE_KEY}");var d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

const isDarkNow = () => document.documentElement.classList.contains("dark");

export function ThemeToggle() {
  // Reads the class set by themeInitScript; the server snapshot assumes light.
  const isDark = useSyncExternalStore(subscribe, isDarkNow, () => false);

  function toggle() {
    const next = !isDark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
    } catch {
      // Storage can be blocked (private mode); the toggle still works for this visit.
    }
  }

  return (
    <Button
      variant="ghost"
      className="h-10 w-full justify-start gap-3 px-3 text-muted-foreground"
      aria-pressed={isDark}
      onClick={toggle}
    >
      {isDark ? (
        <Sun className="size-[18px]" strokeWidth={1.5} aria-hidden="true" />
      ) : (
        <Moon className="size-[18px]" strokeWidth={1.5} aria-hidden="true" />
      )}
      Dark mode
    </Button>
  );
}

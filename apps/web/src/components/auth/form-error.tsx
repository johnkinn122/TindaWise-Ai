"use client";

import { useEffect, useRef } from "react";

/** Error summary at the top of an auth form; receives focus so screen readers announce it. */
export function FormError({ message, version }: { message?: string; version: unknown }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (message) ref.current?.focus();
  }, [message, version]);

  if (!message) return null;
  return (
    <div
      ref={ref}
      tabIndex={-1}
      role="alert"
      className="rounded-sm border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm font-medium text-destructive outline-none"
    >
      {message}
    </div>
  );
}

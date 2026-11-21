import { FlaskConical } from "lucide-react";

/** Shown on every screen that renders src/lib/sample-data.ts, so demo numbers are never mistaken for real ones. */
export function SampleDataBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-info px-2.5 py-0.5 text-xs font-medium text-info">
      <FlaskConical className="size-3" strokeWidth={2} aria-hidden="true" />
      Sample data
    </span>
  );
}

export interface BarListItem {
  key: string;
  label: string;
  /** Drives the bar length; bars are relative to the largest value in the list. */
  value: number;
  /** The figure printed at the end of the row. */
  display: string;
  detail?: string;
}

/**
 * Ranked horizontal bars as a plain list: name, figure, then a bar in one hue (MASTER.md chart-1).
 * The text carries every value, so the bars are decorative for screen readers. No chart library:
 * nothing here needs axes, and the list reads correctly without CSS.
 */
export function BarList({ items, label }: { items: BarListItem[]; label: string }) {
  const max = Math.max(...items.map((item) => Math.abs(item.value)), 0);
  return (
    <ul aria-label={label} className="grid gap-3.5 px-4 py-4 sm:px-5">
      {items.map((item) => (
        <li key={item.key} className="grid gap-1.5">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 font-medium">{item.label}</span>
            <span className="tabular shrink-0 font-semibold">{item.display}</span>
          </div>
          <div aria-hidden="true" className="h-2">
            <div
              className="h-2 rounded-full bg-[var(--chart-1)]"
              style={{ width: `${max > 0 ? Math.max((Math.abs(item.value) / max) * 100, item.value ? 2 : 0) : 0}%` }}
            />
          </div>
          {item.detail && <p className="text-xs text-muted-foreground">{item.detail}</p>}
        </li>
      ))}
    </ul>
  );
}

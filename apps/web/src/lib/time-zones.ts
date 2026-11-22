/**
 * Time zone choices for store settings: every IANA zone the runtime knows, labelled with its
 * current UTC offset ("Asia/Manila (GMT+8)"). Pure, so it is unit-tested.
 */

export interface TimeZoneOption {
  value: string;
  label: string;
}

/** "GMT+8" for `zone` at `when` (offsets change with daylight saving, so it's "now"). */
export function utcOffset(zone: string, when: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "shortOffset" }).formatToParts(
    when,
  );
  return parts.find((part) => part.type === "timeZoneName")?.value ?? "";
}

/**
 * All zones, alphabetical. `current` is always included, even if this runtime doesn't list it
 * (an older ICU), so the select never silently shows a different zone than the one saved.
 */
export function timeZoneOptions(current: string, when: Date = new Date()): TimeZoneOption[] {
  const zones = new Set(Intl.supportedValuesOf("timeZone"));
  zones.add(current);
  return [...zones].sort().map((zone) => {
    const offset = utcOffset(zone, when);
    const name = zone.replaceAll("_", " ");
    return { value: zone, label: offset ? `${name} (${offset})` : name };
  });
}

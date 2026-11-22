import "server-only";

import { apiFetch } from "./client";
import type { Overview } from "./types";

/** Everything the Overview screen shows, in one request. Cashiers get their own sales, no costs. */
export function getOverview(): Promise<Overview> {
  return apiFetch<Overview>("/overview");
}

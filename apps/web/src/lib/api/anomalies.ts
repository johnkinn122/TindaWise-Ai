import "server-only";

import { apiFetch } from "./client";
import type { Anomalies } from "./types";

/** Unusual sales days in the last 7 complete store days. Owners and managers only (403 for cashiers). */
export function getAnomalies(): Promise<Anomalies> {
  return apiFetch<Anomalies>("/anomalies");
}

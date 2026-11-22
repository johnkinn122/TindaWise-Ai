import "server-only";

import { apiFetch } from "./client";
import type { ReportPreset, ReportProductSort, SalesReport } from "./types";

export interface ReportParams {
  preset?: ReportPreset;
  start?: string;
  end?: string;
  sort?: ReportProductSort;
  /** How many top products; exports ask for all of them. */
  top?: number;
}

export function getSalesReport(params: ReportParams): Promise<SalesReport> {
  return apiFetch<SalesReport>("/reports/sales", {
    query: { preset: params.preset, start: params.start, end: params.end, product_sort: params.sort, top: params.top },
  });
}

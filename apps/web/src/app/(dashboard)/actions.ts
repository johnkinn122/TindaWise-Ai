"use server";

import { refresh } from "next/cache";
import { apiFetch } from "@/lib/api/client";
import type { AnomalyAlert } from "@/lib/api/types";
import { type FormState, toFormState } from "@/lib/form-state";

/**
 * Server Actions for the Overview. The API checks the role and that the alert is on the current
 * list; this passes the request through and turns refusals into a message.
 */

export interface DismissAnomalyInput {
  product_id: string;
  day: string;
  kind: AnomalyAlert["kind"];
  note: string;
}

/** Dismiss one "Worth a look" alert. Dismissing it twice is harmless: the API keeps the first. */
export async function dismissAnomalyAction(input: DismissAnomalyInput): Promise<FormState> {
  try {
    await apiFetch("/anomalies/dismissals", {
      method: "POST",
      body: { ...input, note: input.note.trim() || null },
    });
  } catch (error) {
    return toFormState(error);
  }
  refresh();
  return { status: "success" };
}

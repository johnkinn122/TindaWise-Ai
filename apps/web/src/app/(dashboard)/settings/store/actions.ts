"use server";

import { refresh } from "next/cache";
import { apiFetch } from "@/lib/api/client";
import type { Store } from "@/lib/api/types";
import { type FormState, formText, toFormState } from "@/lib/form-state";

/** Saves store settings. The API checks that the caller is the owner. */
export async function updateStoreAction(_prev: FormState, formData: FormData): Promise<FormState> {
  const values = {
    name: formText(formData, "name"),
    timezone: formText(formData, "timezone"),
    default_lead_time_days: formText(formData, "default_lead_time_days"),
  };
  // A whole number goes as a number; anything else goes as typed so the API names the field.
  const days = values.default_lead_time_days;
  const payload = {
    name: values.name,
    timezone: values.timezone,
    default_lead_time_days: /^\d+$/.test(days) ? Number(days) : days,
  };
  try {
    await apiFetch<Store>("/store", { method: "PATCH", body: payload });
  } catch (error) {
    return toFormState(error, values);
  }
  // Re-render the page and the top bar, which shows the store name.
  refresh();
  return { status: "success", message: "Store settings saved." };
}

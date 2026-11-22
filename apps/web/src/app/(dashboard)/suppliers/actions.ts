"use server";

import { redirect } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
import type { Supplier } from "@/lib/api/types";
import { type FormState, formText, toFormState } from "@/lib/form-state";

/** Server Actions for suppliers. The API checks the role; owners and managers only. */

function supplierPayload(formData: FormData) {
  const values = {
    name: formText(formData, "name"),
    contact_name: formText(formData, "contact_name"),
    phone: formText(formData, "phone"),
    email: formText(formData, "email"),
    notes: formText(formData, "notes"),
    lead_time_days: formText(formData, "lead_time_days"),
  };
  // Blank optional fields are sent as null, which clears them when editing.
  const blankToNull = (value: string) => (value === "" ? null : value);
  // A whole number goes as a number; anything else goes as typed so the API names the field.
  const leadTime = values.lead_time_days;
  const payload = {
    name: values.name,
    contact_name: blankToNull(values.contact_name),
    phone: blankToNull(values.phone),
    email: blankToNull(values.email),
    notes: blankToNull(values.notes),
    lead_time_days: leadTime === "" ? null : /^\d+$/.test(leadTime) ? Number(leadTime) : leadTime,
  };
  return { values, payload };
}

export async function createSupplierAction(_prev: FormState, formData: FormData): Promise<FormState> {
  const { values, payload } = supplierPayload(formData);
  try {
    await apiFetch<Supplier>("/suppliers", { method: "POST", body: payload });
  } catch (error) {
    return toFormState(error, values);
  }
  redirect("/suppliers");
}

export async function updateSupplierAction(
  supplierId: string,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const { values, payload } = supplierPayload(formData);
  try {
    await apiFetch<Supplier>(`/suppliers/${encodeURIComponent(supplierId)}`, { method: "PATCH", body: payload });
  } catch (error) {
    return toFormState(error, values);
  }
  redirect("/suppliers");
}

export async function archiveSupplierAction(supplierId: string): Promise<FormState> {
  try {
    await apiFetch<void>(`/suppliers/${encodeURIComponent(supplierId)}`, { method: "DELETE" });
  } catch (error) {
    return toFormState(error);
  }
  redirect("/suppliers");
}

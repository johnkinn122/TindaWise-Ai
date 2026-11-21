"use server";

import { refresh } from "next/cache";
import { ApiError, ApiUnavailableError, apiFetch } from "@/lib/api/client";

export interface MemberFormState {
  status: "idle" | "error" | "success";
  message?: string;
  fields?: Record<string, string>;
  values?: Record<string, string>;
}

const text = (formData: FormData, key: string) => String(formData.get(key) ?? "").trim();

export async function addMemberAction(_prev: MemberFormState, formData: FormData): Promise<MemberFormState> {
  const values = {
    full_name: text(formData, "full_name"),
    email: text(formData, "email"),
    role: text(formData, "role"),
  };
  try {
    // The API checks that the caller is an owner; this action doesn't trust the page that called it.
    await apiFetch("/members", {
      method: "POST",
      body: { ...values, temporary_password: String(formData.get("temporary_password") ?? "") },
    });
  } catch (error) {
    if (error instanceof ApiError) {
      const fields = { ...error.fields };
      if (fields.temporary_password) fields.temporary_password = "At least 10 characters";
      return { status: "error", message: error.message, fields, values };
    }
    if (error instanceof ApiUnavailableError) {
      return { status: "error", message: "Can't reach Tindawise right now. Try again in a moment.", values };
    }
    throw error;
  }
  refresh();
  return {
    status: "success",
    message: `${values.full_name} was added. Share the temporary password with them in person.`,
  };
}

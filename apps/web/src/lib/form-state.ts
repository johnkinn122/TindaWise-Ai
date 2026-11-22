import { ApiError, ApiUnavailableError } from "@/lib/api/client";

/**
 * What a Server Action returns to its form: field errors stay next to their fields, and the
 * typed values come back so inputs keep what the person entered after an error.
 */
export interface FormState {
  status: "idle" | "error" | "success";
  message?: string;
  fields?: Record<string, string>;
  /** Submitted values, echoed back so inputs keep what the person typed after an error. */
  values?: Record<string, string>;
}

/** API errors become a FormState; anything unexpected is re-thrown to the error page. */
export function toFormState(error: unknown, values?: Record<string, string>): FormState {
  if (error instanceof ApiError) {
    return { status: "error", message: error.message, fields: error.fields, values };
  }
  if (error instanceof ApiUnavailableError) {
    return {
      status: "error",
      message: "Can't reach the Tindawise API. Check that it is running, then try again.",
      values,
    };
  }
  throw error;
}

export const formText = (formData: FormData, key: string) => String(formData.get(key) ?? "").trim();

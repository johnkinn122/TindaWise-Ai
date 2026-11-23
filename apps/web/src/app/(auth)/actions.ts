"use server";

import { redirect } from "next/navigation";
import { ApiError, ApiUnavailableError, apiFetch } from "@/lib/api/client";
import { safeNextPath } from "@/lib/auth/next-path";
import { clearSessionCookie, setSessionCookie } from "@/lib/auth/session";

export interface AuthFormState {
  status: "idle" | "error";
  message?: string;
  fields?: Record<string, string>;
  values?: Record<string, string>;
}

interface SessionCreated {
  token: string;
  expires_at: string;
}

const text = (formData: FormData, key: string) => String(formData.get(key) ?? "").trim();

function toState(error: unknown, values: Record<string, string>): AuthFormState {
  if (error instanceof ApiError) return { status: "error", message: error.message, fields: error.fields, values };
  if (error instanceof ApiUnavailableError) {
    return { status: "error", message: "Can't reach Tindawise right now. Try again in a moment.", values };
  }
  throw error;
}

export async function loginAction(_prev: AuthFormState, formData: FormData): Promise<AuthFormState> {
  // Passwords are never echoed back into the form.
  const values = { email: text(formData, "email") };
  let session: SessionCreated;
  try {
    session = await apiFetch<SessionCreated>("/auth/login", {
      method: "POST",
      body: { email: values.email, password: String(formData.get("password") ?? "") },
      onUnauthenticated: "throw", // here a 401 means "wrong email or password"
    });
  } catch (error) {
    return toState(error, values);
  }
  await setSessionCookie(session.token, session.expires_at);
  redirect(safeNextPath(formData.get("next")));
}

export async function signupAction(_prev: AuthFormState, formData: FormData): Promise<AuthFormState> {
  const values = {
    full_name: text(formData, "full_name"),
    email: text(formData, "email"),
    store_name: text(formData, "store_name"),
  };
  let session: SessionCreated;
  try {
    session = await apiFetch<SessionCreated>("/auth/signup", {
      method: "POST",
      body: { ...values, password: String(formData.get("password") ?? "") },
      onUnauthenticated: "throw",
    });
  } catch (error) {
    return toState(error, values);
  }
  await setSessionCookie(session.token, session.expires_at);
  redirect("/");
}

export async function logoutAction() {
  try {
    // Revoke on the server too, so the token is dead even if a copy exists somewhere.
    await apiFetch<void>("/auth/logout", { method: "POST", onUnauthenticated: "throw" });
  } catch {
    // Already expired or API down: still sign out of this browser.
  }
  await clearSessionCookie();
  redirect("/login");
}

/**
 * Starts waking the API while the visitor types. On the free host the API sleeps after 15 idle
 * minutes and takes 30-60 seconds to wake; asking for /health early hides most of that wait.
 * Failures are ignored: signing in reports any real problem.
 */
export async function wakeApiAction(): Promise<void> {
  const url = process.env.API_URL;
  if (!url) return;
  try {
    await fetch(`${url.replace(/\/$/, "")}/health`, { cache: "no-store", signal: AbortSignal.timeout(90_000) });
  } catch {
    // Ignored on purpose: see above.
  }
}


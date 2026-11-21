import "server-only";

import { redirectToLogin } from "@/lib/auth/redirect-to-login";
import { getSessionToken } from "@/lib/auth/session";
import type { ApiErrorBody } from "./types";

/**
 * Server-side client for the Tindawise API.
 *
 * Runs only on the server (Server Components and Server Actions). It forwards the signed-in
 * user's session from the httpOnly cookie as a Bearer token; the API checks it on every request.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** The API could not be reached at all (server down, wrong URL). */
export class ApiUnavailableError extends Error {
  constructor(cause: unknown) {
    super("The Tindawise API is not reachable.", { cause });
    this.name = "ApiUnavailableError";
  }
}

function baseUrl() {
  const url = process.env.API_URL;
  if (!url) throw new Error("API_URL must be set. Copy apps/web/.env.example to .env.local.");
  return url.replace(/\/$/, "");
}

type Query = Record<string, string | number | boolean | undefined | null>;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  query?: Query;
  body?: unknown;
  headers?: Record<string, string>;
  /**
   * What to do when the API says the session is missing or expired.
   * "redirect" (default) sends the person to sign in; "throw" lets the caller handle it
   * (used by the sign-in form itself, where 401 means "wrong password").
   */
  onUnauthenticated?: "redirect" | "throw";
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // Reading the cookie is request-time data, so Next.js never prerenders past this point
  // and the build needs neither the API nor its settings.
  const token = await getSessionToken();
  const url = new URL(`${baseUrl()}/api/v1${path}`);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...(options.body !== undefined && { "Content-Type": "application/json" }),
        ...options.headers,
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });
  } catch (cause) {
    throw new ApiUnavailableError(cause);
  }

  if (response.status === 204) return undefined as T;

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const body = data as Partial<ApiErrorBody> | null;
    const error = new ApiError(
      response.status,
      body?.error?.code ?? "unknown_error",
      body?.error?.message ?? `Request failed with status ${response.status}.`,
      body?.error?.fields ?? {},
    );
    if (error.status === 401 && (options.onUnauthenticated ?? "redirect") === "redirect") {
      redirectToLogin("session");
    }
    throw error;
  }
  return data as T;
}

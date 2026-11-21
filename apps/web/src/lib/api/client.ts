import "server-only";

import type { ApiErrorBody } from "./types";

/**
 * Server-side client for the Tindawise API.
 *
 * Runs only on the server (Server Components and Server Actions), so the API URL and the
 * temporary organization header never reach the browser.
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

function config() {
  const baseUrl = process.env.API_URL;
  const orgId = process.env.TINDAWISE_ORG_ID;
  if (!baseUrl || !orgId) {
    throw new Error("API_URL and TINDAWISE_ORG_ID must be set. Copy apps/web/.env.example to .env.local.");
  }
  return { baseUrl: baseUrl.replace(/\/$/, ""), orgId };
}

type Query = Record<string, string | number | boolean | undefined | null>;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  query?: Query;
  body?: unknown;
  headers?: Record<string, string>;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { baseUrl, orgId } = config();
  const url = new URL(`${baseUrl}/api/v1${path}`);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        // TODO(auth): replace with the signed-in user's session once authentication exists.
        "X-Organization-Id": orgId,
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
    throw new ApiError(
      response.status,
      body?.error?.code ?? "unknown_error",
      body?.error?.message ?? `Request failed with status ${response.status}.`,
      body?.error?.fields ?? {},
    );
  }
  return data as T;
}

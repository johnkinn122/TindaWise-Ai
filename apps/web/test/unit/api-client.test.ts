import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, ApiUnavailableError, apiFetch } from "@/lib/api/client";

const ORG = "00000000-0000-4000-8000-000000000001";

function jsonResponse(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubEnv("API_URL", "http://api.test/");
    vi.stubEnv("TINDAWISE_ORG_ID", ORG);
  });
  afterEach(() => vi.unstubAllEnvs());

  it("builds the URL, drops empty query values, and sends the organization header", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, { ok: true }));

    await apiFetch("/products", { query: { q: "cola", status: undefined, category_id: "", limit: 20 } });

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toBe("http://api.test/api/v1/products?q=cola&limit=20");
    expect((init?.headers as Record<string, string>)["X-Organization-Id"]).toBe(ORG);
    expect(init?.cache).toBe("no-store");
  });

  it("sends JSON bodies", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(201, { id: "1" }));

    await apiFetch("/products", { method: "POST", body: { name: "Coke" } });

    const init = fetchMock.mock.calls[0]![1]!;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"name":"Coke"}');
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("turns API errors into ApiError with field messages", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(409, {
        error: { code: "conflict", message: "SKU taken.", fields: { sku: "Already used by another product" } },
      }),
    );

    const error = await apiFetch("/products").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "conflict", fields: { sku: "Already used by another product" } });
  });

  it("reports an unreachable API as ApiUnavailableError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    await expect(apiFetch("/products")).rejects.toBeInstanceOf(ApiUnavailableError);
  });

  it("returns undefined for 204 No Content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiFetch("/products/1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("fails loudly when configuration is missing", async () => {
    vi.stubEnv("API_URL", "");
    await expect(apiFetch("/products")).rejects.toThrow(/API_URL and TINDAWISE_ORG_ID must be set/);
  });
});

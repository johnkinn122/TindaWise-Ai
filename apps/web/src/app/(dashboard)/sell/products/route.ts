import { type NextRequest, NextResponse } from "next/server";
import { ApiError, ApiUnavailableError, apiFetch } from "@/lib/api/client";
import type { Page, Product } from "@/lib/api/types";

/**
 * Product lookup for the checkout screen, called from the browser:
 *   ?code=<barcode or SKU>  exact match (barcode scanners), 404 if none
 *   ?q=<text>               name/SKU/barcode search, in-stock first
 *
 * It runs on the server and calls the API with the session cookie, so the browser never
 * talks to the API directly (same rule as every other page).
 */
export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code")?.trim().slice(0, 64);
  const q = request.nextUrl.searchParams.get("q")?.trim().slice(0, 100);

  try {
    if (code) {
      const product = await apiFetch<Product>("/products/lookup", { query: { code }, onUnauthenticated: "throw" });
      return NextResponse.json({ items: [product] });
    }
    if (!q) return NextResponse.json({ items: [] });
    const page = await apiFetch<Page<Product>>("/products", {
      query: { q, sort: "-stock", limit: 12 },
      // Called by fetch(), not a page: answer 401 as JSON and let the screen send the person to sign in.
      onUnauthenticated: "throw",
    });
    return NextResponse.json({ items: page.items });
  } catch (error) {
    if (error instanceof ApiError) {
      return NextResponse.json({ error: { code: error.code, message: error.message } }, { status: error.status });
    }
    if (error instanceof ApiUnavailableError) {
      return NextResponse.json(
        { error: { code: "unavailable", message: "Can't reach Tindawise right now." } },
        { status: 503 },
      );
    }
    throw error;
  }
}

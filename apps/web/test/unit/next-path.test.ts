import { describe, expect, it } from "vitest";
import { safeNextPath } from "@/lib/auth/next-path";

describe("safeNextPath", () => {
  it.each([
    ["/products", "/products"],
    ["/products?status=low_stock", "/products?status=low_stock"],
  ])("keeps in-app path %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });

  it.each([
    "https://evil.example",
    "//evil.example",
    String.raw`/\evil.example`, // browsers treat "/\" like "//"
    "javascript:alert(1)",
    "",
    undefined,
    42,
  ])("refuses open redirect %s", (input) => {
    expect(safeNextPath(input)).toBe("/");
  });
});

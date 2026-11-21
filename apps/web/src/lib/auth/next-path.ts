/** Only allow redirects back into this app: "/products" yes, "//evil.com" or "https://…" no. */
export function safeNextPath(value: unknown): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return "/";
  }
  return value;
}

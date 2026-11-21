import { type NextRequest, NextResponse } from "next/server";

/**
 * Optimistic gate: no session cookie → go to sign-in before rendering anything.
 *
 * This only checks that a cookie exists. It is NOT the security boundary: the API validates
 * the session (and role) on every request, and an expired cookie still ends at /login.
 */
const PUBLIC_PATHS = ["/login", "/signup"];
const SESSION_COOKIE = "tw_session"; // keep in sync with lib/auth/session.ts

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))) {
    return NextResponse.next();
  }
  if (!request.cookies.has(SESSION_COOKIE)) {
    const login = new URL("/login", request.url);
    if (pathname !== "/") login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  // Everything except Next.js internals and static files.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)"],
};

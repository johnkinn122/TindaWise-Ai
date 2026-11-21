import "server-only";

import { cookies } from "next/headers";

/**
 * The session token lives in an httpOnly cookie: page scripts can't read it, so an XSS bug
 * can't steal it. Next.js reads it on the server and forwards it to the API as a Bearer token.
 */
export const SESSION_COOKIE = "tw_session";

export async function getSessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

/** Only callable from Server Actions and Route Handlers (Next.js rule for writing cookies). */
export async function setSessionCookie(token: string, expiresAt: string) {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
}

export async function clearSessionCookie() {
  (await cookies()).delete(SESSION_COOKIE);
}

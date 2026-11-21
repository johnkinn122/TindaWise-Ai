import "server-only";

import { redirect } from "next/navigation";

/** Kept in its own module so unit tests can replace it (there is no request to redirect). */
export function redirectToLogin(reason: "session"): never {
  redirect(`/login?reason=${reason}`);
}

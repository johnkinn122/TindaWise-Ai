import "server-only";

import { cache } from "react";
import { apiFetch } from "@/lib/api/client";

export type Role = "owner" | "manager" | "cashier";

export interface CurrentUser {
  user: { id: string; email: string; full_name: string };
  organization: { id: string; name: string; currency: string };
  role: Role;
}

/**
 * The signed-in person, their store and role. Wrapped in React `cache`, so every component in
 * one request shares a single API call. Redirects to /login when the session is missing or over.
 *
 * Call it inside a <Suspense> boundary: it reads the session cookie, which is request-time data.
 */
export const getCurrentUser = cache(() => apiFetch<CurrentUser>("/auth/me"));

/** Owners and managers run products and stock; cashiers look things up (and will sell). */
export const canManageInventory = (role: Role) => role === "owner" || role === "manager";
export const canManageTeam = (role: Role) => role === "owner";
/** Store settings: owners change them, managers can look (the API enforces both). */
export const canEditStore = (role: Role) => role === "owner";

export const roleLabels: Record<Role, string> = {
  owner: "Owner",
  manager: "Manager",
  cashier: "Cashier",
};

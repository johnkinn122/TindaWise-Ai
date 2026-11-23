import "server-only";

/**
 * The public demo (docs/DEPLOYMENT.md). With DEMO_MODE=true the app shows a "public demo"
 * banner, lists the demo accounts on the sign-in page and turns sign-up off (the API refuses
 * it too). Server-side only: no NEXT_PUBLIC_ prefix.
 */
export function isDemo(): boolean {
  return process.env.DEMO_MODE === "true";
}

export interface DemoAccount {
  email: string;
  label: string;
}

/**
 * The accounts created by services/api/scripts/seed.py (and seed_sample_history.py for the
 * store with a sales history). Their password is public on purpose: it's in the seed script.
 */
export const DEMO_PASSWORD = "tindawise-demo";

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { email: "owner@example.com", label: "Owner" },
  { email: "manager@example.com", label: "Manager" },
  { email: "cashier@example.com", label: "Cashier" },
  { email: "sample-owner@example.com", label: "Owner, store with 2 years of sales" },
];

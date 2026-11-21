import { expect, test as setup } from "@playwright/test";
import { DEMO_PASSWORD, STORAGE } from "./demo-accounts";

/**
 * Signs in once per role through the real login form and saves the session cookie, so other
 * tests start signed in. Uses the demo accounts from services/api/scripts/seed.py.
 */
for (const role of ["owner", "cashier"] as const) {
  setup(`sign in as ${role}`, async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: "Email" }).fill(`${role}@example.com`);
    await page.getByLabel("Password").fill(DEMO_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
    await page.context().storageState({ path: STORAGE[role] });
  });
}

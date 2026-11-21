import { expect, test } from "@playwright/test";

// Runs signed in as the owner.

test("the owner adds a cashier, who can then sign in", async ({ page, browser }) => {
  const id = Date.now().toString(36);
  const email = `cashier-${id}@example.com`;

  await page.goto("/");
  await page.getByRole("button", { name: /: Account, / }).click();
  await page.getByRole("menuitem", { name: "Team" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Team" })).toBeVisible();

  await page.getByRole("textbox", { name: "Name" }).fill(`E2E Cashier ${id}`);
  await page.getByRole("textbox", { name: "Email" }).fill(email);
  await page.getByRole("combobox", { name: "Role" }).selectOption("cashier");
  await page.getByLabel("Temporary password").fill("temporary-pass-1");
  await page.getByRole("button", { name: "Add team member" }).click();

  await expect(page.getByText(`E2E Cashier ${id} was added.`)).toBeVisible();
  await expect(page.getByRole("cell", { name: email })).toBeVisible();

  // The new person signs in from a separate, signed-out browser context.
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const other = await context.newPage();
  await other.goto("/login");
  await other.getByRole("textbox", { name: "Email" }).fill(email);
  await other.getByLabel("Password").fill("temporary-pass-1");
  await other.getByRole("button", { name: "Sign in" }).click();
  await expect(other.getByRole("button", { name: /: Account, .*Cashier$/ })).toBeVisible();
  await context.close();
});

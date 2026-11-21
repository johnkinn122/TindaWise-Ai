import { expect, type Page, test } from "@playwright/test";
import { DEMO_PASSWORD } from "./demo-accounts";

// These tests start signed out and sign in with their own sessions, so signing out here never
// revokes the sessions other tests share.
test.use({ storageState: { cookies: [], origins: [] } });

async function signIn(page: Page, email: string, password: string) {
  await page.getByRole("textbox", { name: "Email" }).fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("signed-out visitors are sent to sign in, then back where they were going", async ({ page }) => {
  await page.goto("/products?status=low_stock");
  await expect(page).toHaveURL(/\/login\?next=/);

  await signIn(page, "owner@example.com", DEMO_PASSWORD);
  await expect(page).toHaveURL(/\/products\?status=low_stock$/);
  await expect(page.getByRole("heading", { level: 1, name: "Products" })).toBeVisible();
});

test("a wrong password shows one message that doesn't say which part was wrong", async ({ page }) => {
  await page.goto("/login");
  await signIn(page, "owner@example.com", "not-the-password");

  // Scoped to <main>: Next.js adds its own role="alert" route announcer to every page.
  const alert = page.getByRole("main").getByRole("alert");
  await expect(alert).toHaveText("Email or password is incorrect.");
  await expect(alert).toBeFocused();
  await expect(page.getByRole("textbox", { name: "Email" })).toHaveValue("owner@example.com");
  await expect(page.getByLabel("Password")).toHaveValue("");
});

test("sign up creates a store and signs in as its owner", async ({ page }) => {
  const id = Date.now().toString(36);
  await page.goto("/signup");
  await page.getByRole("textbox", { name: "Your name" }).fill("E2E Owner");
  await page.getByRole("textbox", { name: "Store name" }).fill(`E2E Store ${id}`);
  await page.getByRole("textbox", { name: "Email" }).fill(`e2e-${id}@example.com`);
  await page.getByLabel("Password").fill("a-long-enough-password");
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  await expect(page.getByRole("banner").getByText(`E2E Store ${id}`)).toBeVisible();
  // A brand-new store has no products: the store's data is its own.
  await page.goto("/products");
  await expect(page.getByRole("heading", { name: "Add your first product" })).toBeVisible();
});

test("sign up refuses an email that already has an account", async ({ page }) => {
  await page.goto("/signup");
  await page.getByRole("textbox", { name: "Your name" }).fill("Someone");
  await page.getByRole("textbox", { name: "Store name" }).fill("Another store");
  await page.getByRole("textbox", { name: "Email" }).fill("owner@example.com");
  await page.getByLabel("Password").fill("a-long-enough-password");
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByText("Already has an account")).toBeVisible();
});

test("signing out ends the session", async ({ page }) => {
  await page.goto("/login");
  await signIn(page, "manager@example.com", DEMO_PASSWORD);
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();

  await page.getByRole("button", { name: /: Account, / }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto("/products");
  await expect(page).toHaveURL(/\/login/);
});

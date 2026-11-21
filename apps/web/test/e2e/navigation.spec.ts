import { expect, test } from "@playwright/test";

test("overview labels its numbers as sample data", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  await expect(page.getByText("Sample data")).toBeVisible();
  await expect(page.getByRole("region", { name: "Restock 3 items before Monday" })).toBeVisible();
});

test("the first Tab reaches the skip link, which jumps to main content", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
});

test("sidebar marks the current page", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" });
  await nav.getByRole("link", { name: "Products" }).click();
  await expect(page).toHaveURL(/\/products$/);
  await expect(nav.getByRole("link", { name: "Products" })).toHaveAttribute("aria-current", "page");
  await expect(nav.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current", "page");
});

test("planned modules say they are planned", async ({ page }) => {
  await page.goto("/suppliers");
  await expect(page.getByRole("heading", { name: "Suppliers is planned" })).toBeVisible();
});

test("the top bar shows the signed-in store and person", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("banner").getByText("Aling Nena's Mini-Mart (sample)")).toBeVisible();
  await expect(page.getByRole("button", { name: "NS: Account, Nena Santos, Owner" })).toBeVisible();
});

test("dark mode toggle switches theme and is remembered", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Dark mode" });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await toggle.click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
});

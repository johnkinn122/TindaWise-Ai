import { expect, test } from "@playwright/test";

test("overview shows the store's real figures, not sample data", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  await expect(page.getByText("Sample data")).toHaveCount(0);
  await expect(page.getByText("Gross margin today")).toBeVisible();
  // The seed has products below their reorder level (e.g. Coca-Cola 1.5L is out of stock).
  const watch = page.getByRole("region", { name: "Stock to watch" });
  await expect(watch.getByRole("cell", { name: "Coca-Cola 1.5L" })).toBeVisible();
  const reorder = page.getByRole("region", { name: "Reorder suggestions" });
  await expect(reorder.getByText("Coca-Cola 1.5L")).toBeVisible();
  await expect(reorder.getByText("Estimated cost")).toBeVisible();
  await expect(reorder.getByText(/covers the delivery time plus 10 days/)).toBeVisible();
  // Coca-Cola has never been in stock, so there's no sales rate: it falls back to the reorder level.
  const coke = reorder.getByRole("listitem").filter({ hasText: "Coca-Cola 1.5L" });
  await expect(coke.getByText(/^0 on hand · little sales history yet/)).toBeVisible();
  await expect(coke.getByText("24 btl")).toBeVisible();
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

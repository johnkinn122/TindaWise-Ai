import { expect, test } from "@playwright/test";

test("the drawer menu navigates and closes on a phone", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation" }).click();
  const drawer = page.getByRole("dialog");
  await drawer.getByRole("link", { name: "Products" }).click();

  await expect(page).toHaveURL(/\/products$/);
  await expect(drawer).toBeHidden();
});

test("the product list fits the screen and shows stock status", async ({ page }) => {
  await page.goto("/products");
  await expect(page.getByRole("link", { name: "Coca-Cola 1.5L" })).toBeVisible();
  // Status column is hidden on phones; the badge moves under the name.
  await expect(page.getByRole("table").getByText("Out of stock").first()).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the inventory ledger fits the screen and keeps change and balance", async ({ page }) => {
  await page.goto("/inventory");
  await expect(page.getByRole("heading", { name: "Stock changes" })).toBeVisible();
  // When, reason and source fold under the product name; the two numbers stay as columns.
  await expect(page.getByRole("columnheader", { name: "Change" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Balance" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "When" })).toBeHidden();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

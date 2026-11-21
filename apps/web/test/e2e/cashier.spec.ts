import { expect, test } from "@playwright/test";

// Runs in the "cashier" project: signed in as cashier@example.com.

test("a cashier can browse products but not change them", async ({ page }) => {
  await page.goto("/products");
  await expect(page.getByRole("link", { name: "Coca-Cola 1.5L" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Add product" })).toHaveCount(0);

  await page.getByRole("link", { name: "Coca-Cola 1.5L" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Coca-Cola 1.5L" })).toBeVisible();
  await expect(page.getByText("Only owners and managers can change stock.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Edit" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Archive" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add stock" })).toHaveCount(0);
});

test("a cashier who opens the add-product page directly is told why they can't", async ({ page }) => {
  await page.goto("/products/new");
  await expect(page.getByText("Only owners and managers can add products.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add product" })).toHaveCount(0);
});

test("a cashier has no Team menu and can't open the team page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /: Account, .*Cashier$/ }).click();
  await expect(page.getByRole("menuitem", { name: "Team" })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await page.goto("/settings/team");
  await expect(page.getByText("Only the store owner can manage the team.")).toBeVisible();
});

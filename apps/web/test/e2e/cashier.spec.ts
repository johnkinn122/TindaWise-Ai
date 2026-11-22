import { expect, test } from "@playwright/test";

// Runs in the "cashier" project: signed in as cashier@example.com.

test("a cashier can browse products but not change them", async ({ page }) => {
  await page.goto("/products");
  await expect(page.getByRole("link", { name: "Coca-Cola 1.5L" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Add product" })).toHaveCount(0);

  await page.getByRole("link", { name: "Coca-Cola 1.5L" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Coca-Cola 1.5L" })).toBeVisible();
  await expect(page.getByText("Only owners and managers can change stock.")).toBeVisible();
  // Costs are for owners and managers; the API doesn't send them to cashiers.
  await expect(page.getByText("Selling price")).toBeVisible();
  await expect(page.getByText("Cost", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Margin per unit")).toHaveCount(0);
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

test("a cashier's overview shows their own sales and no costs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Your sales today")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your sales this week" })).toBeVisible();
  await expect(page.getByText(/gross margin/i)).toHaveCount(0);
  const reorder = page.getByRole("region", { name: "Reorder suggestions" });
  await expect(reorder.getByText("Coca-Cola 1.5L")).toBeVisible();
  await expect(reorder.getByText("Estimated cost")).toHaveCount(0);
  await expect(reorder.getByRole("button", { name: "Create purchase order" })).toHaveCount(0);
});

test("a cashier can't see suppliers or purchase orders", async ({ page }) => {
  await page.goto("/suppliers");
  await expect(page.getByText("Only owners and managers can see suppliers and purchase orders.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Add supplier" })).toHaveCount(0);
  await page.goto("/purchase-orders");
  await expect(page.getByText("Only owners and managers can see purchase orders.")).toBeVisible();
  await expect(page.getByRole("link", { name: "New purchase order" })).toHaveCount(0);
});

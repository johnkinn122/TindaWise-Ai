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
  await expect(page.getByRole("menuitem", { name: "Store settings" })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await page.goto("/settings/team");
  await expect(page.getByText("Only the store owner can manage the team.")).toBeVisible();
  await page.goto("/settings/store");
  await expect(page.getByText("Only the store owner and managers can see store settings.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: /Store name/ })).toHaveCount(0);
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

test("a cashier can't open reports", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByText("Reports show costs and profit, so only owners and managers can see them.")).toBeVisible();
  const response = await page.request.get("/reports/export?kind=products");
  expect(response.status()).toBe(403);
});

test("a cashier sees their own sales history but can't give refunds", async ({ page }) => {
  await page.goto("/sales");
  await expect(page.getByRole("heading", { level: 1, name: "Sales history" })).toBeVisible();
  await expect(page.getByText("Your receipts, newest first. Refunds are given by an owner or manager.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Refund items" })).toHaveCount(0);

  // Even with a direct link, the refund page explains the rule (the API refuses it too).
  await page.goto("/sales/00000000-0000-0000-0000-000000000000/refund");
  await expect(page.getByText("Only owners and managers can give refunds.")).toBeVisible();
});

test("a cashier can't open the inventory ledger", async ({ page }) => {
  await page.goto("/inventory");
  await expect(page.getByText(/only owners and managers can see it/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stock changes" })).toHaveCount(0);
  await expect(page.getByText("Stock value", { exact: true })).toHaveCount(0); // the KPI label, not the notice
});

import { expect, test } from "@playwright/test";

// Runs signed in as the owner. Makes its own entries by changing a store setting and putting it
// back, so the demo store ends as it started.

test("the owner sees store changes in the activity log", async ({ page }) => {
  const days = page.getByRole("textbox", { name: /Default delivery time/ });
  const save = page.getByRole("button", { name: "Save settings" });
  const status = page.getByRole("status");

  await page.goto("/settings/store");
  await days.fill("4");
  await save.click();
  await expect(status).toHaveText("Store settings saved.");
  await days.fill("3");
  await save.click();
  await expect(status).toHaveText("Store settings saved.");

  await page.getByRole("button", { name: /: Account, / }).click();
  await page.getByRole("menuitem", { name: "Activity log" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Activity log" })).toBeVisible();

  await page.getByRole("combobox", { name: "Show" }).selectOption("store.updated");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page).toHaveURL(/action=store\.updated/);
  const rows = page.getByRole("row").filter({ hasText: "Changed store settings: default delivery time" });
  // Newest first: the change back to 3 days, then the change to 4.
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(2);
  await expect(rows.first().getByRole("link", { name: "Open settings" })).toHaveAttribute("href", "/settings/store");

  await page.getByRole("combobox", { name: "Show" }).selectOption("purchase_order.closed");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("row").filter({ hasText: "Changed store settings" })).toHaveCount(0);
});

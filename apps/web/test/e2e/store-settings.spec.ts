import { expect, type Page, test } from "@playwright/test";

// Runs signed in as the owner. Every test shares the demo store, so this one puts the original
// values back at the end, even if an assertion fails.

const ORIGINAL_NAME = "Aling Nena's Mini-Mart (sample)";

const nameBox = (page: Page) => page.getByRole("textbox", { name: /Store name/ });
const daysBox = (page: Page) => page.getByRole("textbox", { name: /Default delivery time/ });
const save = (page: Page) => page.getByRole("button", { name: "Save settings" }).click();

test("the owner renames the store and sets the default delivery time", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /: Account, / }).click();
  await page.getByRole("menuitem", { name: "Store settings" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Store settings" })).toBeVisible();

  await expect(nameBox(page)).toHaveValue(ORIGINAL_NAME);
  await expect(page.getByRole("combobox", { name: "Time zone" })).toHaveValue("Asia/Manila");
  await expect(page.getByRole("option", { name: "Asia/Manila (GMT+8)" })).toBeAttached();
  await expect(daysBox(page)).toHaveValue("3");
  await expect(page.getByText("PHP", { exact: true })).toBeVisible();

  try {
    // Out of range: the API's message lands on the field, and the typed value is kept.
    await daysBox(page).fill("61");
    await save(page);
    await expect(page.getByRole("alert").getByText("Some fields need attention.")).toBeVisible();
    await expect(page.getByText(/less than or equal to 60/)).toBeVisible();
    await expect(daysBox(page)).toHaveValue("61");

    await nameBox(page).fill("Nena's Store (renamed by e2e)");
    await daysBox(page).fill("5");
    await save(page);
    await expect(page.getByRole("status")).toHaveText("Store settings saved.");
    // The top bar shows the new name without a reload.
    await expect(page.getByRole("banner").getByText("Nena's Store (renamed by e2e)")).toBeVisible();

    await page.reload();
    await expect(nameBox(page)).toHaveValue("Nena's Store (renamed by e2e)");
    await expect(daysBox(page)).toHaveValue("5");
  } finally {
    await page.goto("/settings/store");
    await nameBox(page).fill(ORIGINAL_NAME);
    await daysBox(page).fill("3");
    await save(page);
    await expect(page.getByRole("status")).toHaveText("Store settings saved.");
  }
});

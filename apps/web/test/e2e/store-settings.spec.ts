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

test("times on screen follow the store's time zone", async ({ page }) => {
  const zone = page.getByRole("combobox", { name: "Time zone" });
  const setZone = async (value: string) => {
    await page.goto("/settings/store");
    await zone.selectOption(value);
    await save(page);
    await expect(page.getByRole("status")).toHaveText("Store settings saved.");
  };
  // The change to Honolulu makes its own activity entry; read its time in both zones.
  const entry = (nth: number) =>
    page.getByRole("row").filter({ hasText: "Changed store settings: time zone" }).nth(nth).getByRole("cell").first();

  try {
    await setZone("Pacific/Honolulu");
    await page.goto("/settings/activity?action=store.updated");
    const inHonolulu = await entry(0).innerText();

    await setZone("Asia/Manila");
    await page.goto("/settings/activity?action=store.updated");
    // Newest first: [0] is the change back to Manila, [1] the change to Honolulu read above.
    const inManila = await entry(1).innerText();

    // Same moment, shown 18 hours apart (Manila UTC+8, Honolulu UTC-10, no daylight saving).
    const hours = (Date.parse(inManila.replace(/\s+/g, " ")) - Date.parse(inHonolulu.replace(/\s+/g, " "))) / 3_600_000;
    expect(hours).toBe(18);
  } finally {
    await setZone("Asia/Manila");
  }
});

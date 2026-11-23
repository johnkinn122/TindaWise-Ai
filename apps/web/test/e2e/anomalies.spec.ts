import { expect, test } from "@playwright/test";

// Runs in the "desktop" project: signed in as the owner of the demo store.
// The demo products have too little history for the check (14 in-stock days are needed), so
// the list itself is covered by API and unit tests; this checks the panel reaches the Overview.

test("the owner sees the Worth a look panel on the Overview, with how it works", async ({ page }) => {
  await page.goto("/");
  const panel = page.getByRole("region", { name: "Worth a look" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/Nothing unusual in the last 7 days\.|stands? out in the last 7 days\./)).toBeVisible();
  await expect(panel.getByText(/compared with its average on days it was in stock over the previous 28 days/)).toBeVisible();
  // Stock going missing: depends on count corrections other tests may have made, so either state.
  await expect(panel.getByRole("heading", { level: 3, name: "Stock going missing" })).toBeVisible();
  await expect(
    panel.getByText(/No stock count in the last 8 weeks found 5% or more|in stock counts over the last 8 weeks\./),
  ).toBeVisible();
  await expect(panel.getByText(/Damage you recorded doesn.t count/)).toBeVisible();
});

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
});

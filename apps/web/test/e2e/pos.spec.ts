import { expect, type Page, test } from "@playwright/test";

// Runs in the "cashier" project: selling is the cashier's main job.

const scanBox = (page: Page) => page.getByRole("searchbox", { name: "Scan a barcode or search products" });
const cart = (page: Page) => page.getByRole("region", { name: "Cart" });

async function stockOf(page: Page, name: string): Promise<number> {
  await page.goto("/products");
  await page.getByRole("searchbox", { name: "Search" }).and(page.locator(":enabled")).fill(name);
  const row = page.getByRole("row").filter({ has: page.getByRole("link", { name, exact: true }) });
  await expect(row).toHaveCount(1);
  return Number((await row.getByRole("cell").nth(3).innerText()).split(/\s/)[0]!.replace(/,/g, ""));
}

test("a cashier scans, searches, takes cash and prints a receipt", async ({ page }) => {
  const detergentBefore = await stockOf(page, "Surf Powder Detergent 65g");

  await page.goto("/sell");
  // A barcode scanner types the code and presses Enter; an SKU works the same way.
  await scanBox(page).fill("HSE-002");
  await scanBox(page).press("Enter");
  await expect(cart(page).getByText("Surf Powder Detergent 65g")).toBeVisible();
  await expect(scanBox(page)).toBeFocused();
  await expect(scanBox(page)).toHaveValue("");

  // Typing a name shows results to click.
  await scanBox(page).fill("sardines");
  await page.getByRole("button", { name: /555 Sardines Tomato Sauce 155g/ }).click();

  // Two detergents: ₱9.00 × 2 + ₱24.00 = ₱42.00
  await cart(page).getByRole("button", { name: "One more Surf Powder Detergent 65g" }).click();
  await expect(page.getByRole("button", { name: "Complete sale · ₱42.00" })).toBeDisabled(); // no cash yet

  await page.getByRole("button", { name: "₱50.00" }).click();
  await expect(page.getByText("₱8.00")).toBeVisible(); // change
  await page.getByRole("button", { name: "Complete sale · ₱42.00" }).click();

  const receipt = page.getByRole("region", { name: /^Receipt S-\d{6}$/ });
  await expect(receipt).toBeVisible();
  await expect(receipt).toContainText("Aling Nena's Mini-Mart (sample)");
  await expect(receipt).toContainText("2 × ₱9.00");
  await expect(receipt).toContainText("Cashier: Carlo Dizon");
  await expect(page.getByRole("button", { name: "New sale" })).toBeFocused();

  expect(await stockOf(page, "Surf Powder Detergent 65g")).toBe(detergentBefore - 2);
});

test("cash below the total can't complete the sale", async ({ page }) => {
  await page.goto("/sell");
  await scanBox(page).fill("CAN-001");
  await scanBox(page).press("Enter");
  await page.getByRole("textbox", { name: "Cash received (₱)" }).fill("10");

  await expect(page.getByText("Short by ₱14.00")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Complete sale/ })).toBeDisabled();
});

test("an e-wallet sale needs a reference number", async ({ page }) => {
  await page.goto("/sell");
  await scanBox(page).fill("CAN-001");
  await scanBox(page).press("Enter");
  // Payment is disabled until the scanned item is in the cart. `force` (needed for the visually
  // hidden radio) skips Playwright's enabled check, so wait for the cart first.
  await expect(cart(page).getByText("1 item")).toBeVisible();
  await page.getByRole("radio", { name: "E-wallet" }).check({ force: true });

  const complete = page.getByRole("button", { name: /^Complete sale/ });
  await expect(complete).toBeDisabled();
  await page.getByRole("textbox", { name: "Reference number" }).fill("GC-0042");
  await complete.click();

  const receipt = page.getByRole("region", { name: /^Receipt S-\d{6}$/ });
  await expect(receipt).toContainText("GC-0042");
});

test("an unknown barcode says so and adds nothing", async ({ page }) => {
  await page.goto("/sell");
  await scanBox(page).fill("0000000000000");
  await scanBox(page).press("Enter");
  await expect(page.getByText("No product with barcode or SKU “0000000000000”.")).toBeVisible();
  await expect(cart(page).getByText("Scan or search to add the first item.")).toBeVisible();
});

test("out-of-stock products can't be added", async ({ page }) => {
  await page.goto("/sell");
  await scanBox(page).fill("Coca-Cola");
  await expect(page.getByRole("button", { name: /Coca-Cola 1\.5L/ })).toBeDisabled();
});

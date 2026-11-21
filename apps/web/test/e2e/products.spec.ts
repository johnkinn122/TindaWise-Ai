import { expect, type Page, test } from "@playwright/test";

/**
 * Full product lifecycle against the real API. Each run uses a unique SKU, and the product is
 * archived at the end, so repeated runs don't collide.
 */
const runId = Date.now().toString(36).toUpperCase();
const sku = `E2E-${runId}`;
const name = `E2E test product ${runId}`;

/**
 * Role-based locators only: with Cache Components a previously visited page can stay in the DOM
 * (hidden), and getByRole ignores hidden elements while getByLabel does not.
 */
async function fillProduct(page: Page, values: Record<string, string>) {
  for (const [name, value] of Object.entries(values)) {
    await page.getByRole("textbox", { name }).or(page.getByRole("spinbutton", { name })).fill(value);
  }
}

const field = (page: Page, name: string) =>
  page.getByRole("textbox", { name }).or(page.getByRole("spinbutton", { name }));
const stockRegion = (page: Page) => page.getByRole("region", { name: "Stock", exact: true });
const productSearch = (page: Page) => page.getByRole("searchbox", { name: "Search" }).and(page.locator(":enabled"));

test.describe.serial("product lifecycle", () => {
  let productUrl = "";

  test("create a product with opening stock", async ({ page }) => {
    await page.goto("/products");
    await page.getByRole("link", { name: "Add product" }).first().click();
    await expect(page.getByRole("heading", { level: 1, name: "Add product" })).toBeVisible();

    await fillProduct(page, {
      "Product name": name,
      SKU: sku,
      "Selling price": "25.50",
      Cost: "20.00",
      "Reorder level": "5",
      "Opening stock": "8",
    });
    await page.getByRole("combobox", { name: "Category" }).selectOption({ label: "Snacks" });
    await page.getByRole("button", { name: "Add product" }).click();

    await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
    productUrl = page.url();
    await expect(stockRegion(page).getByText("8", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Details" }).getByText("₱5.50 (21.6%)")).toBeVisible();
    await expect(page.getByRole("region", { name: "Stock history" }).getByText("Opening stock")).toBeVisible();
  });

  test("receive stock from a supplier", async ({ page }) => {
    await page.goto(productUrl);
    await page.getByRole("combobox", { name: "Reason" }).selectOption({ label: "Received from supplier" });
    await field(page, "Quantity to add").fill("12");
    await page.getByRole("textbox", { name: "Note" }).fill("Delivery receipt 0042");
    await page.getByRole("button", { name: "Add stock" }).click();

    await expect(page.getByText("Stock updated. New balance: 20.")).toBeVisible();
    await expect(stockRegion(page).getByText("20", { exact: true })).toBeVisible();
    await expect(page.getByText("Delivery receipt 0042")).toBeVisible();
  });

  test("removing more than on hand is refused with a clear message", async ({ page }) => {
    await page.goto(productUrl);
    await page.getByRole("combobox", { name: "Reason" }).selectOption({ label: "Damaged or expired" });
    await field(page, "Quantity to remove").fill("999");
    await page.getByRole("button", { name: "Remove stock" }).click();

    await expect(page.getByText("More than the stock on hand")).toBeVisible();
    await expect(stockRegion(page).getByText("20", { exact: true })).toBeVisible();
  });

  test("edit the selling price", async ({ page }) => {
    await page.goto(productUrl);
    await page.getByRole("link", { name: "Edit" }).click();
    await expect(field(page, "Product name")).toHaveValue(name);
    await field(page, "Selling price").fill("27.00");
    await page.getByRole("button", { name: "Save changes" }).click();

    await expect(page).toHaveURL(productUrl);
    await expect(page.getByRole("region", { name: "Details" }).getByText("₱27.00")).toBeVisible();
  });

  test("find it by search, then archive it", async ({ page }) => {
    await page.goto("/products");
    await productSearch(page).fill(sku);
    await expect(page).toHaveURL(new RegExp(`q=${sku}`));
    await page.getByRole("link", { name }).click();

    await page.getByRole("button", { name: "Archive" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText(`Archive ${name}?`);
    await dialog.getByRole("button", { name: "Archive product" }).click();

    await expect(page).toHaveURL(/\/products$/);
    await productSearch(page).fill(sku);
    await expect(page.getByText("No products match these filters")).toBeVisible();
  });
});

test("an empty form shows field errors and focuses the summary", async ({ page }) => {
  await page.goto("/products/new");
  await page.getByRole("button", { name: "Add product" }).click();

  const summary = page.getByRole("alert").filter({ hasText: "Some fields need attention." });
  await expect(summary).toBeFocused();
  await expect(field(page, "Product name")).toHaveAttribute("aria-invalid", "true");
  await expect(field(page, "Selling price")).toHaveAttribute("aria-invalid", "true");
});

test("a duplicate SKU is reported under the SKU field, and typed values are kept", async ({ page }) => {
  await page.goto("/products/new");
  await fillProduct(page, { "Product name": "Duplicate check", SKU: "NDL-001", "Selling price": "10" });
  await page.getByRole("button", { name: "Add product" }).click();

  await expect(page.getByText("Already used by another product")).toBeVisible();
  await expect(field(page, "SKU")).toHaveAttribute("aria-invalid", "true");
  await expect(field(page, "Product name")).toHaveValue("Duplicate check");
});

test("filters are kept in the URL", async ({ page }) => {
  await page.goto("/products");
  await page.getByRole("combobox", { name: "Stock" }).selectOption({ label: "Out of stock" });
  await expect(page).toHaveURL(/status=out_of_stock/);
  await expect(page.getByRole("link", { name: "Coca-Cola 1.5L" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Datu Puti Vinegar 1L" })).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("combobox", { name: "Stock" })).toHaveValue("out_of_stock");
});

test("an unknown product shows a not-found page", async ({ page }) => {
  await page.goto("/products/00000000-0000-4000-8000-0000000000ff");
  await expect(page.getByRole("heading", { name: "Product not found" })).toBeVisible();
});

import { expect, type Page, test } from "@playwright/test";

/**
 * Reports against the real API, signed in as the owner. The test sells a product it creates
 * itself (unique per run), so it doesn't depend on, or change, seeded stock other tests use.
 */
const runId = Date.now().toString(36).toUpperCase();
const productName = `Report test product ${runId}`;
const sku = `RPT-${runId}`;

const textbox = (page: Page, name: string | RegExp) => page.getByRole("textbox", { name });

test.describe.serial("reports", () => {
  test("a sale today shows up in today's report", async ({ page }) => {
    await page.goto("/products/new");
    await textbox(page, /Product name/).fill(productName);
    await textbox(page, /SKU/).fill(sku);
    await textbox(page, /Selling price/).fill("50.00");
    await textbox(page, /Cost/).fill("30.00");
    await page.getByRole("textbox", { name: /Opening stock/ }).or(page.getByRole("spinbutton", { name: /Opening stock/ })).fill("5");
    await page.getByRole("button", { name: "Add product" }).click();
    await expect(page.getByRole("heading", { level: 1, name: productName })).toBeVisible();

    await page.goto("/sell");
    const scan = page.getByRole("searchbox", { name: "Scan a barcode or search products" });
    await scan.fill(sku);
    await scan.press("Enter");
    await expect(page.getByRole("region", { name: "Cart" }).getByText(productName)).toBeVisible();
    await page.getByRole("button", { name: "Exact" }).click();
    await page.getByRole("button", { name: /^Complete sale/ }).click();
    await expect(page.getByRole("region", { name: /^Receipt S-\d{6}$/ })).toBeVisible();

    await page.goto("/reports?preset=today");
    await expect(page.getByRole("link", { name: "Today", exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByText("Gross margin", { exact: true })).toBeVisible();
    const products = page.getByRole("region", { name: "Top products" });
    await expect(products.getByRole("link", { name: productName })).toBeVisible();
    await expect(page.getByRole("region", { name: "Sales by day" }).getByRole("img")).toBeVisible();
  });

  test("sorting the products table is announced and kept in the URL", async ({ page }) => {
    await page.goto("/reports?preset=today");
    const products = page.getByRole("region", { name: "Top products" });
    await expect(products.getByRole("columnheader", { name: /Sales/ })).toHaveAttribute("aria-sort", "descending");
    await products.getByRole("link", { name: /Gross profit/ }).click();
    await expect(page).toHaveURL(/sort=gross_profit/);
    await expect(products.getByRole("columnheader", { name: /Gross profit/ })).toHaveAttribute("aria-sort", "descending");
  });

  test("the chart has a table view and the products download as CSV", async ({ page }) => {
    await page.goto("/reports?preset=today");
    const chart = page.getByRole("region", { name: "Sales by day" });
    await chart.getByRole("button", { name: "View as table" }).click();
    await expect(chart.getByRole("columnheader", { name: "Gross profit" })).toBeVisible();

    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download all (CSV)" }).click();
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/^tindawise-products-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.csv$/);
    const text = await (await file.createReadStream()).toArray().then((chunks) => Buffer.concat(chunks).toString("utf8"));
    expect(text).toContain("Product,SKU,Unit,Quantity,Sales (PHP),Gross profit (PHP),Gross margin (%)");
    expect(text).toContain(`${productName},${sku},pcs,1,50.00,20.00,40.0`);
  });
});

test("a custom range is checked and explained", async ({ page }) => {
  await page.goto("/reports?start=2026-02-01&end=2026-01-01");
  await expect(page.getByText("The end date is before the start date.")).toBeVisible();
  await page.goto("/reports?start=2026-01-01&end=2026-01-31");
  await expect(page.getByText(/Jan 1\s*–\s*31, 2026/).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Last 7 days" })).not.toHaveAttribute("aria-current", "page");
});

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * The store-wide inventory ledger against the real API, signed in as the owner. The test creates
 * its own product (unique per run) and sells it, so seeded stock that other tests use isn't touched.
 */
const runId = Date.now().toString(36).toUpperCase();
const productName = `Ledger test product ${runId}`;
const sku = `LDG-${runId}`;
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

const textbox = (page: Page, name: string | RegExp) => page.getByRole("textbox", { name });
const ledgerRows = (page: Page) => page.getByRole("row").filter({ has: page.getByRole("link", { name: productName, exact: true }) });

test.describe.serial("inventory ledger", () => {
  let receiptCode = "";

  test("a new product and its sale appear in the ledger, linked to the receipt", async ({ page }) => {
    await page.goto("/products/new");
    await textbox(page, /Product name/).fill(productName);
    await textbox(page, /SKU/).fill(sku);
    await textbox(page, /Selling price/).fill("20.00");
    await textbox(page, /Cost/).fill("12.00");
    await page.getByRole("textbox", { name: /Opening stock/ }).or(page.getByRole("spinbutton", { name: /Opening stock/ })).fill("5");
    await page.getByRole("button", { name: "Add product" }).click();
    await expect(page.getByRole("heading", { level: 1, name: productName })).toBeVisible();

    await page.goto("/sell");
    const scan = page.getByRole("searchbox", { name: "Scan a barcode or search products" });
    await scan.fill(sku);
    await scan.press("Enter");
    await expect(page.getByRole("region", { name: "Cart" }).getByText(productName)).toBeVisible();
    await page.getByRole("button", { name: "Exact" }).click();
    await page.getByRole("button", { name: "Complete sale · ₱20.00" }).click();
    const receipt = page.getByRole("region", { name: /^Receipt S-\d{6}$/ });
    await expect(receipt).toBeVisible();
    receiptCode = (await receipt.getByRole("heading").innerText()).replace("Receipt ", "");

    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Inventory" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Inventory" })).toBeVisible();
    await expect(page.getByText("Stock value")).toBeVisible();

    await page.getByRole("searchbox", { name: "Product" }).fill(sku.toLowerCase());
    await page.getByRole("button", { name: "Show" }).click();
    // Empty fields are dropped from the URL, so it says only what is filtered.
    await expect(page).toHaveURL(new RegExp(`/inventory\\?q=${sku.toLowerCase()}$`));

    const rows = ledgerRows(page);
    await expect(rows).toHaveCount(2);
    const [sold, opening] = [rows.nth(0), rows.nth(1)];
    await expect(sold.getByRole("cell", { name: "Sold" })).toBeVisible();
    await expect(sold.getByRole("cell", { name: "−1" })).toBeVisible();
    await expect(sold.getByRole("cell", { name: "Nena Santos" })).toBeVisible();
    await expect(opening.getByRole("cell", { name: "Opening stock" })).toBeVisible();
    await expect(opening.getByRole("cell", { name: "+5" })).toBeVisible();

    await sold.getByRole("link", { name: `Receipt ${receiptCode}` }).click();
    await expect(page.getByRole("heading", { level: 1, name: `Receipt ${receiptCode}` })).toBeVisible();
  });

  test("filters by reason, and a product page opens its own ledger", async ({ page }) => {
    await page.goto(`/inventory?q=${sku}`);
    await page.getByRole("combobox", { name: "Reason" }).selectOption("initial");
    await page.getByRole("button", { name: "Show" }).click();
    await expect(page).toHaveURL(/reason=initial/);
    await expect(ledgerRows(page)).toHaveCount(1);
    await expect(ledgerRows(page).getByRole("cell", { name: "Opening stock" })).toBeVisible();

    await page.goto(`/products?q=${sku}`);
    await page.getByRole("link", { name: productName, exact: true }).click();
    await page.getByRole("link", { name: "See all in Inventory" }).click();
    await expect(page).toHaveURL(/\/inventory\?product=/);
    await expect(page.getByText("Showing one product:")).toBeVisible();
    await expect(ledgerRows(page)).toHaveCount(2);

    const results = await new AxeBuilder({ page }).include("#main").withTags(TAGS).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);

    await page.getByRole("link", { name: `Show all products, not just ${productName}` }).click();
    await expect(page).toHaveURL(/\/inventory$/);
    await expect(page.getByText("Showing one product:")).toHaveCount(0);
  });

  test("a date range that ends before it starts is explained", async ({ page }) => {
    await page.goto("/inventory?start=2026-11-22&end=2026-11-01");
    await expect(page.locator("#main").getByRole("alert")).toHaveText("The end date is before the start date.");
  });

  test("no matches says so and offers a way back", async ({ page }) => {
    await page.goto(`/inventory?q=${sku}&reason=damage`);
    await expect(page.getByRole("heading", { name: "No stock changes match" })).toBeVisible();
    await page.getByRole("link", { name: "Clear filters" }).click();
    await expect(page).toHaveURL(/\/inventory$/);
  });
});

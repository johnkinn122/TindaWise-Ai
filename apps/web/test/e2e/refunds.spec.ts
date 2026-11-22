import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * Sales history and refunds against the real API, signed in as the owner. The test creates its own
 * product and sale (unique per run), so seeded stock that other tests use isn't touched.
 */
const runId = Date.now().toString(36).toUpperCase();
const productName = `Refund test product ${runId}`;
const sku = `RFD-${runId}`;
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

const textbox = (page: Page, name: string | RegExp) => page.getByRole("textbox", { name });

async function stockOf(page: Page): Promise<number> {
  await page.goto(`/products?q=${sku}`);
  const row = page.getByRole("row").filter({ has: page.getByRole("link", { name: productName, exact: true }) });
  await expect(row).toHaveCount(1);
  // "On hand" reads like "2pcs" (number and unit in separate spans), so take the leading number.
  return Number.parseInt((await row.getByRole("cell").nth(3).innerText()).replace(/,/g, ""), 10);
}

async function noAxeViolations(page: Page) {
  // Scan only the visible page: the previous route may remain in the DOM, hidden by <Activity>.
  const results = await new AxeBuilder({ page }).include("#main").withTags(TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

test.describe.serial("sales history and refunds", () => {
  let receiptCode = "";

  test("a sale shows up in sales history and can be found by its number", async ({ page }) => {
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
    const cart = page.getByRole("region", { name: "Cart" });
    await expect(cart.getByText(productName)).toBeVisible();
    await cart.getByRole("button", { name: `One more ${productName}` }).click();
    await cart.getByRole("button", { name: `One more ${productName}` }).click();
    await page.getByRole("button", { name: "Exact" }).click();
    await page.getByRole("button", { name: "Complete sale · ₱60.00" }).click();
    const receipt = page.getByRole("region", { name: /^Receipt S-\d{6}$/ });
    await expect(receipt).toBeVisible();
    receiptCode = (await receipt.getByRole("heading").innerText()).replace("Receipt ", "");

    await page.getByRole("link", { name: "Sales history" }).first().click();
    await expect(page.getByRole("heading", { level: 1, name: "Sales history" })).toBeVisible();
    await page.getByRole("textbox", { name: "Find a receipt" }).fill(receiptCode.toLowerCase());
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page).toHaveURL(/receipt=/);
    await page.getByRole("link", { name: receiptCode }).click();

    await expect(page.getByRole("heading", { level: 1, name: `Receipt ${receiptCode}` })).toBeVisible();
    await expect(page.getByText("Paid", { exact: true }).filter({ visible: true })).toBeVisible();
    await noAxeViolations(page);
  });

  test("an unknown receipt number is explained, not an error page", async ({ page }) => {
    await page.goto("/sales?receipt=R-12");
    await expect(page.locator("#main").getByRole("alert")).toHaveText("Enter a receipt number like S-000123 or 123.");
    await page.goto("/sales?receipt=999999999");
    await expect(page.getByRole("heading", { name: "No receipt 999999999" })).toBeVisible();
  });

  test("a partial refund asks first, then puts the item back in stock", async ({ page }) => {
    expect(await stockOf(page)).toBe(2);
    await page.goto(`/sales?receipt=${receiptCode}`);
    await page.getByRole("link", { name: receiptCode }).click();
    await page.getByRole("link", { name: "Refund items" }).click();
    await expect(page.getByRole("heading", { level: 1, name: `Refund on ${receiptCode}` })).toBeVisible();

    // Nothing chosen yet: the problems are listed and focused, and each field says what's wrong.
    await page.getByRole("button", { name: "Review refund" }).click();
    const problems = page.locator("#main").getByRole("alert");
    await expect(problems).toBeFocused();
    await expect(problems).toContainText("Fix 1 problem to continue.");
    await expect(problems.getByRole("link", { name: "Choose a reason" })).toBeVisible();
    await noAxeViolations(page);

    await page.getByRole("radio", { name: /Customer returned it/ }).check();
    await page.getByRole("button", { name: "Review refund" }).click();
    await expect(page.locator("#main").getByRole("alert")).toHaveText("Enter how many to refund for at least one item.");

    const quantity = page.getByRole("textbox", { name: new RegExp(`^Refund \\(pcs\\) of ${productName}`) });
    await quantity.fill("4");
    await page.getByRole("button", { name: "Review refund" }).click();
    await expect(page.locator("#main").getByRole("alert")).toContainText("Only 3 left to refund");

    await quantity.fill("1");
    await expect(page.getByText("₱20.00", { exact: true }).filter({ visible: true })).toBeVisible(); // the running total
    await page.getByRole("button", { name: "Review refund" }).click();
    const dialog = page.getByRole("alertdialog", { name: "Refund ₱20.00?" });
    await expect(dialog).toContainText(`Give ₱20.00 back in cash for 1 item on receipt ${receiptCode}. Everything goes back in stock.`);
    await dialog.getByRole("button", { name: "Refund ₱20.00" }).click();

    await expect(page.getByRole("heading", { level: 1, name: `Receipt ${receiptCode}` })).toBeVisible();
    await expect(page.getByRole("status")).toContainText(/Refund R-\d{6} recorded\. Give back ₱20\.00 in cash\./);
    await expect(page.getByText("Partly refunded").filter({ visible: true })).toBeVisible();
    const refunds = page.getByRole("region", { name: "Refunds" });
    await expect(refunds).toContainText("Customer returned it");
    await expect(refunds).toContainText(`1 × ${productName} · back in stock`);
    await expect(page.getByRole("row", { name: /Kept/ })).toContainText("₱40.00");

    expect(await stockOf(page)).toBe(3);
  });

  test("refunding the rest without restocking closes the receipt and leaves stock alone", async ({ page }) => {
    await page.goto(`/sales?receipt=${receiptCode}`);
    await page.getByRole("link", { name: receiptCode }).click();
    await page.getByRole("link", { name: "Refund items" }).click();

    await page.getByRole("button", { name: "Refund everything" }).click();
    await expect(page.getByRole("textbox", { name: new RegExp(`of ${productName}`) })).toHaveValue("2");
    await page.getByRole("checkbox", { name: `Back on shelf (${productName})` }).uncheck();
    await page.getByRole("radio", { name: /Damaged or spoiled/ }).check();
    await page.getByRole("button", { name: "Review refund" }).click();
    const dialog = page.getByRole("alertdialog", { name: "Refund ₱40.00?" });
    await expect(dialog).toContainText("Nothing goes back in stock.");
    await dialog.getByRole("button", { name: "Refund ₱40.00" }).click();

    await expect(page.getByRole("status")).toContainText("Give back ₱40.00 in cash.");
    // The status badge is the first "Refunded" on the page (the items table also has a Refunded column).
    await expect(page.getByText("Refunded", { exact: true }).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByText("Partly refunded").filter({ visible: true })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Refund items" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Refunds" })).toContainText(`2 × ${productName} · not restocked`);

    await page.goto(`/sales?receipt=${receiptCode}`);
    await expect(page.getByRole("row", { name: new RegExp(receiptCode) })).toContainText("−₱60.00 refunded");

    expect(await stockOf(page)).toBe(3); // damaged units don't come back
  });

  test("today's report shows sales net of the refunds", async ({ page }) => {
    await page.goto("/reports?preset=today");
    await expect(page.getByText(/^Gross sales ₱[\d,]+\.\d{2} − \d+ refunds? ₱[\d,]+\.\d{2} = net sales -?₱[\d,]+\.\d{2}$/)).toBeVisible();
    await expect(page.getByText("Net sales", { exact: true }).filter({ visible: true })).toBeVisible();
  });
});

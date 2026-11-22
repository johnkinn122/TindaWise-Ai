import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * Suppliers and purchase orders against the real API, signed in as the owner.
 * The receiving test makes its own product and supplier (unique per run), so the seeded stock
 * other tests rely on (e.g. Coca-Cola out of stock) is never changed.
 */
const runId = Date.now().toString(36).toUpperCase();
const productName = `PO test product ${runId}`;
const supplierName = `PO test supplier ${runId}`;

const textbox = (page: Page, name: string | RegExp) => page.getByRole("textbox", { name });
const heading = (page: Page, name: string | RegExp) => page.getByRole("heading", { level: 1, name });

test.describe.serial("buying from a supplier", () => {
  let orderUrl = "";

  test("add a supplier and a product to order", async ({ page }) => {
    await page.goto("/suppliers/new");
    await textbox(page, /Supplier name/).fill(supplierName);
    await textbox(page, "Contact person").fill("Ana Cruz");
    await textbox(page, "Phone").fill("0917 555 0101");
    await page.getByRole("button", { name: "Add supplier" }).click();
    await expect(page.getByRole("link", { name: supplierName })).toBeVisible();

    await page.goto("/products/new");
    await textbox(page, /Product name/).fill(productName);
    await textbox(page, /SKU/).fill(`PO-${runId}`);
    await textbox(page, /Selling price/).fill("20.00");
    await textbox(page, /Cost/).fill("10.00");
    await page.getByRole("button", { name: "Add product" }).click();
    await expect(heading(page, productName)).toBeVisible();
  });

  test("draft an order, then approve it", async ({ page }) => {
    await page.goto("/purchase-orders/new");
    await page.getByRole("combobox", { name: "Supplier" }).selectOption({ label: supplierName });
    await page.getByRole("searchbox", { name: "Add a product" }).fill(productName);
    await page.getByRole("button", { name: new RegExp(productName) }).click();
    await textbox(page, `Quantity (pcs) of ${productName}`).fill("6");
    await textbox(page, `Unit cost (₱) of ${productName}`).fill("12.50");
    await expect(page.getByText("₱75.00").first()).toBeVisible(); // 6 × ₱12.50
    await page.getByRole("button", { name: "Create draft" }).click();

    await expect(heading(page, /^PO-\d{6}$/)).toBeVisible();
    orderUrl = page.url();
    await expect(page.getByText("Draft", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Approve" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("₱75.00");
    await dialog.getByRole("button", { name: "Approve order" }).click();
    await expect(page.getByText("Approved", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit" })).toHaveCount(0); // lines are locked
  });

  test("receive a short delivery, then the rest", async ({ page }) => {
    await page.goto(orderUrl);
    const delivery = page.getByRole("region", { name: "Record a delivery" });
    await textbox(page, `Arrived (pcs) of ${productName}`).fill("4");
    await delivery.getByRole("button", { name: "Record delivery" }).click();
    await expect(delivery.getByText("Delivery recorded. Stock and costs are updated.")).toBeVisible();
    await expect(page.getByText("Partly received", { exact: true }).first()).toBeVisible();
    await expect(textbox(page, `Arrived (pcs) of ${productName}`)).toHaveValue("2"); // what's still owed

    await delivery.getByRole("button", { name: "Record delivery" }).click();
    await expect(page.getByText("Received", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Record a delivery" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Deliveries" }).getByRole("listitem")).toHaveCount(4); // 2 × (delivery + line)

    // Stock went up by 6 and the product's cost is now the order's cost (latest-cost rule).
    await page.getByRole("link", { name: productName }).click();
    await expect(heading(page, productName)).toBeVisible();
    await expect(page.getByRole("region", { name: "Stock", exact: true }).getByText("6", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Details" }).getByText("₱12.50", { exact: true })).toBeVisible();
  });

  test("the order page has no detectable WCAG A/AA violations", async ({ page }) => {
    await page.goto(orderUrl);
    await expect(heading(page, /^PO-\d{6}$/)).toBeVisible();
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .include("#main")
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});

test("the Overview drafts an order from reorder suggestions, which can be cancelled", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("region", { name: "Reorder suggestions" }).getByRole("button", { name: "Create purchase order" }).click();
  await expect(heading(page, /^Edit PO-\d{6}$/)).toBeVisible();
  // The seed has Coca-Cola out of stock with a reorder level of 12: suggest 24.
  await expect(textbox(page, "Quantity (btl) of Coca-Cola 1.5L")).toHaveValue("24");

  await page.getByRole("link", { name: "Cancel" }).click();
  await expect(heading(page, /^PO-\d{6}$/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel order" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel order" }).click();
  await expect(page.getByText("Cancelled", { exact: true }).first()).toBeVisible();
});

test("the order list filters by status", async ({ page }) => {
  await page.goto("/purchase-orders?status=cancelled");
  await expect(page.getByRole("link", { name: "Cancelled", exact: true })).toHaveAttribute("aria-current", "page");
  // Phones show the badge inside the first cell instead; at desktop width that copy is hidden.
  await expect(page.getByRole("table").getByText("Cancelled", { exact: true }).filter({ visible: true }).first()).toBeVisible();
});

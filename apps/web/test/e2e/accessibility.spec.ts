import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/** Automated WCAG 2.2 AA checks (axe-core) in both themes. This catches a subset of issues, not all. */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

function summarize(violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]) {
  return violations.map((v) => ({
    rule: v.id,
    impact: v.impact,
    targets: v.nodes.map((n) => `${n.target.join(" ")} — ${n.failureSummary?.split("\n")[1]?.trim() ?? ""}`).slice(0, 5),
  }));
}

const pages = ["/", "/products", "/products/new", "/suppliers"];

for (const theme of ["light", "dark"] as const) {
  for (const path of pages) {
    test(`${path} has no detectable WCAG A/AA violations (${theme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
      await page.goto(path);
      await page.waitForLoadState("networkidle");

      const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
      expect(summarize(results.violations)).toEqual([]);
    });
  }
}

for (const theme of ["light", "dark"] as const) {
  test(`a product detail page has no detectable WCAG A/AA violations (${theme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
    await page.goto("/products?q=NDL-001");
    await page.getByRole("link", { name: "Lucky Me Pancit Canton (Original)" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Lucky Me Pancit Canton (Original)");
    await page.waitForLoadState("networkidle");

    // Scan only the visible page: the previous route may remain in the DOM, hidden by <Activity>.
    const results = await new AxeBuilder({ page }).include("#main").withTags(TAGS).analyze();
    expect(summarize(results.violations)).toEqual([]);
  });
}

/**
 * B041 F001 — Recommendations simplified-card / professional-table view toggle.
 *
 * Default = simplified cards; the Radix Tabs toggle switches to the existing
 * professional table and back. Data-independent (asserts the toggle's active
 * state, not specific positions, so it passes whether or not the CI account
 * has target positions). The export-to-ticket workflow stays intact. Both
 * locales. The big-number / delta-colour / tooltip details are covered by
 * vitest + the F002 L2 manual browser check.
 */
import { expect, test } from "@playwright/test";

for (const { locale, simpleLabel, professionalLabel } of [
  { locale: "en", simpleLabel: "Simple", professionalLabel: "Professional" },
  { locale: "zh-CN", simpleLabel: "简洁", professionalLabel: "专业" },
]) {
  test(`recommendations view toggle + ${locale} labels`, async ({ page, context }) => {
    await context.addCookies([
      { name: "NEXT_LOCALE", value: locale, domain: "127.0.0.1", path: "/" },
    ]);
    await page.goto("/recommendations");

    await expect(page.getByTestId("recommendations-view-toggle")).toBeVisible();
    const simpleTab = page.getByTestId("view-toggle-simple");
    const proTab = page.getByTestId("view-toggle-professional");
    await expect(simpleTab).toHaveText(simpleLabel);
    await expect(proTab).toHaveText(professionalLabel);

    // Default = simplified card view active.
    await expect(simpleTab).toHaveAttribute("data-state", "active");

    // Toggle to the professional table → it becomes active.
    await proTab.click();
    await expect(proTab).toHaveAttribute("data-state", "active");

    // Toggle back to the simplified cards.
    await simpleTab.click();
    await expect(simpleTab).toHaveAttribute("data-state", "active");

    // The export-to-ticket research workflow is untouched by the toggle.
    await expect(page.getByTestId("recommendations-export")).toBeVisible();
  });
}

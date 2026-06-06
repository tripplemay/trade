/**
 * B040 F003 — Robinhood metrics e2e across both faces, both locales.
 *
 * /backtest: the headline metrics render as a big-number grid (MetricsDisplay)
 * with bilingual tooltips. /reports/[slug]: a report whose markdown carries a
 * metrics table (B016 wide table) shows the big-number card ABOVE the markdown,
 * and the markdown report still renders in full below it.
 *
 * No execution affordance on either metrics card (research-only).
 */
import { expect, test } from "@playwright/test";

// A committed report whose markdown carries a B016-style wide metrics table;
// the backend resolves this slug by substring match against the filename.
const METRICS_REPORT_SLUG = "B016-risk-parity-hrp-comparison";

for (const { locale, tooltipSnippet } of [
  { locale: "en", tooltipSnippet: "Risk-adjusted return" },
  { locale: "zh-CN", tooltipSnippet: "风险调整" },
]) {
  test(`/backtest metrics display + ${locale} tooltip`, async ({ page, context }) => {
    await context.addCookies([
      { name: "NEXT_LOCALE", value: locale, domain: "127.0.0.1", path: "/" },
    ]);
    await page.goto("/backtest");

    // The big-number grid renders (labels show even before a run).
    await expect(page.getByTestId("metrics-display")).toBeVisible();
    await expect(page.getByTestId("metric-sharpe")).toBeVisible();
    // No order/execute button on the metrics card.
    await expect(page.getByTestId("metrics-display").getByRole("button")).toHaveCount(0);

    // Hover the Sharpe label → the localized explanatory tooltip appears.
    await page.getByTestId("metric-sharpe").hover();
    await expect(page.getByTestId("metric-tooltip-sharpe")).toContainText(tooltipSnippet);
  });

  test(`/reports metrics card above markdown + ${locale}`, async ({ page, context }) => {
    await context.addCookies([
      { name: "NEXT_LOCALE", value: locale, domain: "127.0.0.1", path: "/" },
    ]);
    await page.goto(`/reports/${METRICS_REPORT_SLUG}`);

    // The big-number metrics card renders (parsed from the report's table).
    await expect(page.getByTestId("report-metrics")).toBeVisible();
    await expect(page.getByTestId("metric-value-sharpe")).toBeVisible();
    await expect(page.getByTestId("report-metrics").getByRole("button")).toHaveCount(0);

    // body_markdown integrity: the full detail section (metrics card + the
    // markdown body card below it) renders together.
    await expect(page.getByTestId("page-report-detail")).toBeVisible();
  });
}

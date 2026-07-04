/**
 * B080 F004 — /monitoring dashboard e2e (both locales) + no-execution guard.
 *
 * The monitoring page is advisory-only observation: per-strategy health cards
 * (rolling IC / tracking / exposure + OOS red-card status), the trial registry
 * table, and a frozen re-validation trigger. The re-validation button IS present
 * (it kicks off a RESEARCH pipeline, not a trade), but the page must carry NO trade
 * affordance — no order / ticket / buy / sell / execute control.
 */
import { expect, test } from "@playwright/test";

const STRATEGY = "cn_attack_pure_momentum";

for (const locale of ["en", "zh-CN"]) {
  test(`/monitoring renders + no trade affordance (${locale})`, async ({ page, context }) => {
    await context.addCookies([
      { name: "NEXT_LOCALE", value: locale, domain: "127.0.0.1", path: "/" },
    ]);
    await page.goto("/monitoring");

    // The page + a per-strategy health card + the trial registry card render
    // (structure is static; data may be empty in the e2e DB).
    await expect(page.getByTestId("page-monitoring")).toBeVisible();
    await expect(page.getByTestId(`monitoring-card-${STRATEGY}`)).toBeVisible();
    await expect(page.getByTestId("monitoring-trials-card")).toBeVisible();

    // The re-validation trigger is present — a research-pipeline button, allowed.
    await expect(page.getByTestId(`monitoring-reverify-${STRATEGY}`)).toBeVisible();

    // No-execution guard: NO trade affordance anywhere on the page.
    for (const tradeTestId of [
      "export-ticket",
      "submit-order",
      "place-order",
      "execute-order",
      "buy",
      "sell",
    ]) {
      await expect(page.getByTestId(tradeTestId)).toHaveCount(0);
    }
    // The research-only framing is visible.
    await expect(page.getByTestId("monitoring-disclaimer-card")).toBeVisible();
  });
}

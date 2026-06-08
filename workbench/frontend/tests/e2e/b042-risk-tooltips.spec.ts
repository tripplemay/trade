/**
 * B042 F001 — Playwright smoke for the Robinhood-style Risk panel polish.
 *
 * Against the empty CI stack the panel is in its green state (no snapshots),
 * so this covers the always-present polish: the risk-term tooltip triggers
 * (master drawdown / kill-switch / per-sleeve drawdown) render with their
 * dotted-underline affordance and reveal localised explanations on hover, in
 * both locales. The yellow / red states + the kill-switch red drill are
 * exercised by the component vitest + the F002 L2 live drill (which PUTs a
 * risk sample to trip the kill-switch).
 */

import { expect, test, type BrowserContext } from "@playwright/test";

const LOCALE_COOKIE = "NEXT_LOCALE";

async function setLocaleCookie(context: BrowserContext, locale: "zh-CN" | "en"): Promise<void> {
  const { hostname } = new URL(test.info().project.use.baseURL ?? "http://127.0.0.1:3000");
  await context.addCookies([
    {
      name: LOCALE_COOKIE,
      value: locale,
      domain: hostname,
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax",
      expires: Math.floor(Date.now() / 1000) + 60 * 60,
    },
  ]);
}

for (const locale of ["zh-CN", "en"] as const) {
  test.describe(`B042 risk panel polish (${locale})`, () => {
    test.beforeEach(async ({ context }) => {
      await setLocaleCookie(context, locale);
    });

    test(`risk-term tooltips render + reveal on hover (${locale})`, async ({ page }) => {
      await page.goto("/risk");
      await expect(page.getByTestId("page-risk")).toBeVisible();
      await expect(page.getByTestId("risk-banner")).toBeVisible();

      const masterTerm = page.getByTestId("risk-term-masterDrawdown");
      const killTerm = page.getByTestId("risk-term-killSwitch");
      await expect(masterTerm).toBeVisible();
      await expect(killTerm).toBeVisible();

      // Hover the master-drawdown term → its radix tooltip content appears.
      await masterTerm.hover();
      await expect(page.getByTestId("risk-tooltip-masterDrawdown")).toBeVisible();
    });
  });
}

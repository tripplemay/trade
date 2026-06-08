/**
 * B047 F003 — Playwright smoke for the async Backtest page.
 *
 * Against the CI stack there is no backtest worker, so a Run stays queued and
 * the page shows the running state (the done render is covered by the page
 * vitest with a mocked GET, and by the F002/F005 worker on the VM). This pins:
 * the page loads, the Run button enables once strategies load, and clicking it
 * enqueues (the request returns 202) and flips the state line to running — in
 * both locales.
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
  test.describe(`B047 backtest async (${locale})`, () => {
    test.beforeEach(async ({ context }) => {
      await setLocaleCookie(context, locale);
    });

    test(`Run enqueues + shows running state (${locale})`, async ({ page }) => {
      await page.goto("/backtest");
      await expect(page.getByTestId("page-backtest")).toBeVisible();
      const run = page.getByTestId("backtest-run");
      await expect(run).toBeEnabled();
      await run.click();
      // POST /run returns 202 + queued; the page flips to the running state
      // while it polls (no worker in CI → it stays running, then times out).
      await expect(page.getByTestId("backtest-state")).toContainText(/running|运行/);
    });
  });
}

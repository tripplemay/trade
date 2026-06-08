/**
 * B047 F003 + B047-OPS2 F002 — Playwright smoke for the async Backtest page.
 *
 * The CI stack runs a real backend against an empty DB (no data-refresh), so the
 * data-coverage window + a worker error are mocked at the browser layer with
 * `page.route` (the real default-range Run on real data is F003's VM job). This
 * pins, in both locales:
 *  - data-range present → the default window seeds inside the usable band, Run
 *    enables, clicking it enqueues (202) and flips the state line to running;
 *  - data-range empty → the empty-data prompt shows and Run is disabled;
 *  - a structured worker error → a friendly bilingual message (the raw English
 *    `insufficient price history…` exception is never surfaced).
 */

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const LOCALE_COOKIE = "NEXT_LOCALE";

const WINDOW = {
  data_start: "2021-06-01",
  data_end: "2026-06-08",
  min_usable_start: "2022-04-02",
} as const;

const EMPTY_WINDOW = {
  data_start: null,
  data_end: null,
  min_usable_start: null,
} as const;

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

async function mockDataRange(page: Page, body: unknown): Promise<void> {
  await page.route("**/api/backtests/data-range", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

for (const locale of ["zh-CN", "en"] as const) {
  test.describe(`B047 backtest async (${locale})`, () => {
    test.beforeEach(async ({ context }) => {
      await setLocaleCookie(context, locale);
    });

    test(`default range loads + Run enqueues + shows running state (${locale})`, async ({
      page,
    }) => {
      await mockDataRange(page, WINDOW);
      await page.goto("/backtest");
      await expect(page.getByTestId("page-backtest")).toBeVisible();
      // The default window seeds inside the usable band → Run enables.
      await expect(page.getByTestId("backtest-data-coverage")).toBeVisible();
      const run = page.getByTestId("backtest-run");
      await expect(run).toBeEnabled();
      await run.click();
      // POST /run returns 202 + queued; the page flips to running while polling.
      await expect(page.getByTestId("backtest-state")).toContainText(/running|运行/);
    });

    test(`empty data-range shows the empty state + disables Run (${locale})`, async ({ page }) => {
      await mockDataRange(page, EMPTY_WINDOW);
      await page.goto("/backtest");
      await expect(page.getByTestId("backtest-empty-data")).toBeVisible();
      await expect(page.getByTestId("backtest-run")).toBeDisabled();
    });

    test(`structured worker error → friendly message, not the raw exception (${locale})`, async ({
      page,
    }) => {
      await mockDataRange(page, WINDOW);
      await page.route("**/api/backtests/run", (route) =>
        route.fulfill({
          status: 202,
          contentType: "application/json",
          body: JSON.stringify({ run_id: "bt-e2e", status: "queued" }),
        }),
      );
      await page.route("**/api/backtests/bt-e2e", (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            run_id: "bt-e2e",
            status: "error",
            error: "insufficient price history for any signal date in range",
            error_kind: "insufficient_history",
          }),
        }),
      );
      await page.goto("/backtest");
      const run = page.getByTestId("backtest-run");
      await expect(run).toBeEnabled();
      await run.click();
      const state = page.getByTestId("backtest-state");
      // The friendly copy references the usable-start date in both locales…
      await expect(state).toContainText("2022-04-02");
      // …and never leaks the raw English worker exception.
      await expect(state).not.toContainText("insufficient price history");
    });
  });
}

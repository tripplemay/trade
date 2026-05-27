/**
 * B026 / B030 — Playwright smoke for the decommissioned synthetic banner.
 *
 * B026 originally shipped the banner and required it to render. B030
 * milestone A / Layer 0→1 explicitly turns it off in production and
 * removes the protected-layout render path. The component file remains
 * in the tree for rollback, but the live app must not surface the banner.
 *
 * Acceptance (B030 F003/F004):
 *   - sampled protected routes do not render `synthetic-data-banner`
 *   - zh-CN / en locale changes do not resurrect the banner
 *
 * Uses the same auth storageState + locale-cookie pattern as
 * tests/e2e/b025-us-quality-bilingual.spec.ts.
 */

import { expect, test, type BrowserContext } from "@playwright/test";

const LOCALE_COOKIE = "NEXT_LOCALE";
const BANNER_TESTID = "synthetic-data-banner";
const SAMPLE_ROUTES = ["/", "/strategies", "/risk", "/reports", "/backtest"] as const;

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

test.describe("B026 SyntheticDataBanner decommissioned (zh-CN)", () => {
  test.beforeEach(async ({ context }) => {
    await setLocaleCookie(context, "zh-CN");
  });

  test("banner is absent on /strategies", async ({ page }) => {
    await page.goto("/strategies");
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);
  });

  test("banner is absent on every sampled protected route", async ({ page }) => {
    for (const route of SAMPLE_ROUTES) {
      await page.goto(route);
      await expect(
        page.getByTestId(BANNER_TESTID),
        `decommissioned banner unexpectedly present on ${route}`,
      ).toHaveCount(0);
    }
  });

  test("reload does not resurrect the banner", async ({ page }) => {
    await page.goto("/strategies");
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);
  });
});

test.describe("B026 SyntheticDataBanner decommissioned (en)", () => {
  test.beforeEach(async ({ context }) => {
    await setLocaleCookie(context, "en");
  });

  test("banner is absent on /strategies", async ({ page }) => {
    await page.goto("/strategies");
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);
  });

  test("locale switch does not resurrect the banner", async ({ page, context }) => {
    await context.clearCookies({ name: LOCALE_COOKIE });
    await setLocaleCookie(context, "zh-CN");
    await page.goto("/risk");
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);

    await context.clearCookies({ name: LOCALE_COOKIE });
    await setLocaleCookie(context, "en");
    await page.reload();
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);
  });
});

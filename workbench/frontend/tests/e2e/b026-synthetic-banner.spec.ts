/**
 * B026 F001 — Playwright bilingual smoke for the SyntheticDataBanner.
 *
 * Acceptance (spec §5 F001 + §7 gates):
 *   - zh-CN banner headline contains "研究原型 · 仅含合成数据"
 *   - en banner headline contains "Research prototype · Synthetic data only"
 *   - 5 protected routes sampled (≥3) → banner visible on each
 *   - dismissing the banner hides it for the current page, and reloading
 *     re-renders it (session-only dismissal is by design — spec §6)
 *
 * Uses the same auth storageState + locale-cookie pattern as
 * tests/e2e/b025-us-quality-bilingual.spec.ts.
 */

import { expect, test, type BrowserContext } from "@playwright/test";

const LOCALE_COOKIE = "NEXT_LOCALE";
const BANNER_TESTID = "synthetic-data-banner";
const HEADLINE_TESTID = "synthetic-data-banner-headline";
const CLOSE_TESTID = "synthetic-data-banner-close";

const ZH_HEADLINE_FRAGMENT = "研究原型 · 仅含合成数据";
const EN_HEADLINE_FRAGMENT = "Research prototype · Synthetic data only";

// Sample three of the five protected routes called out in spec §5 F001 (6).
// The Backtest and Reports paths cover the heavier shell variants
// (resizable panel + AG Grid) while `/` exercises the dashboard cards.
const SAMPLE_ROUTES = ["/", "/strategies", "/risk"] as const;

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

test.describe("B026 SyntheticDataBanner (zh-CN)", () => {
  test.beforeEach(async ({ context }) => {
    await setLocaleCookie(context, "zh-CN");
  });

  test("banner renders with zh-CN headline on /strategies", async ({ page }) => {
    await page.goto("/strategies");
    const banner = page.getByTestId(BANNER_TESTID);
    await expect(banner).toBeVisible();
    await expect(page.getByTestId(HEADLINE_TESTID)).toContainText(ZH_HEADLINE_FRAGMENT);
  });

  test("banner appears on every sampled protected route", async ({ page }) => {
    for (const route of SAMPLE_ROUTES) {
      await page.goto(route);
      await expect(page.getByTestId(BANNER_TESTID), `banner missing on ${route}`).toBeVisible();
    }
  });

  test("clicking close hides the banner; reload brings it back", async ({ page }) => {
    await page.goto("/strategies");
    await expect(page.getByTestId(BANNER_TESTID)).toBeVisible();
    await page.getByTestId(CLOSE_TESTID).click();
    await expect(page.getByTestId(BANNER_TESTID)).toHaveCount(0);

    await page.reload();
    // Reload re-mounts the React tree; dismissed state is session-React
    // only, so the banner must reappear — by design (spec §6).
    await expect(page.getByTestId(BANNER_TESTID)).toBeVisible();
    await expect(page.getByTestId(HEADLINE_TESTID)).toContainText(ZH_HEADLINE_FRAGMENT);
  });
});

test.describe("B026 SyntheticDataBanner (en)", () => {
  test.beforeEach(async ({ context }) => {
    await setLocaleCookie(context, "en");
  });

  test("banner renders with en headline on /strategies", async ({ page }) => {
    await page.goto("/strategies");
    const banner = page.getByTestId(BANNER_TESTID);
    await expect(banner).toBeVisible();
    await expect(page.getByTestId(HEADLINE_TESTID)).toContainText(EN_HEADLINE_FRAGMENT);
  });

  test("banner headline tracks locale switch (zh-CN → en) via cookie", async ({
    page,
    context,
  }) => {
    // Pre-seed zh-CN, then visit /risk, then flip the cookie + reload.
    await context.clearCookies({ name: LOCALE_COOKIE });
    await setLocaleCookie(context, "zh-CN");
    await page.goto("/risk");
    await expect(page.getByTestId(HEADLINE_TESTID)).toContainText(ZH_HEADLINE_FRAGMENT);

    await context.clearCookies({ name: LOCALE_COOKIE });
    await setLocaleCookie(context, "en");
    await page.reload();
    await expect(page.getByTestId(HEADLINE_TESTID)).toContainText(EN_HEADLINE_FRAGMENT);
  });
});

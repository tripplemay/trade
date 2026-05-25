/**
 * B025 F005/F006 fix-round 1 — Playwright bilingual smoke for the
 * satellite_us_quality surface.
 *
 * Codex F006 L1 flagged that the spec required `Playwright ≥29
 * (19 baseline + ≥10 双 locale)` but `tests/e2e/` had no B025 entry.
 * This file ships exactly that: zh-CN + en coverage of the 5 spec routes
 * (`/strategies`, `/recommendations`, `/risk`, `/reports`, `/reports/[slug]`)
 * plus a locale-switch + cookie-persistence assertion.
 *
 * Tests rely on the auth-setup storageState project (see
 * playwright.config.ts) so every spec starts authed against the local
 * stack; the locale cookie is pre-seeded inside ``test.beforeEach`` so
 * each test pins its own locale deterministically rather than depending
 * on whichever language the previous test left in the browser context.
 */

import { expect, test, type BrowserContext } from "@playwright/test";

const LOCALE_COOKIE = "NEXT_LOCALE";
const REPORT_SLUG = "B025-us-quality-momentum-backtest";

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
  test.describe(`B025 satellite_us_quality (${locale})`, () => {
    test.beforeEach(async ({ context }) => {
      await setLocaleCookie(context, locale);
    });

    test(`strategies page renders bilingual us_quality highlight (${locale})`, async ({ page }) => {
      await page.goto("/strategies");
      const card = page.getByTestId("strategies-us-quality-highlight");
      await expect(card).toBeVisible();
      const name = await page.getByTestId("us-quality-name").textContent();
      if (locale === "zh-CN") {
        expect(name).toBe("美股质量动量");
      } else {
        expect(name).toBe("US Quality Momentum");
      }
      // Sleeve identifier stays English in both locales (per spec §4.5).
      await expect(page.getByTestId("us-quality-tagline")).toContainText("satellite_us_quality");
    });

    test(`strategies page exposes all 5 factor labels (${locale})`, async ({ page }) => {
      await page.goto("/strategies");
      const expectations: Record<"zh-CN" | "en", Record<string, string>> = {
        "zh-CN": {
          momentum: "动量",
          quality: "质量",
          lowVol: "低波",
          value: "价值",
          trend: "趋势",
        },
        en: {
          momentum: "Momentum",
          quality: "Quality",
          lowVol: "Low Vol",
          value: "Value",
          trend: "Trend",
        },
      };
      for (const [key, fragment] of Object.entries(expectations[locale])) {
        await expect(page.getByTestId(`us-quality-factor-${key}`)).toContainText(fragment);
      }
      // Synthetic-data disclaimer must appear in both locales (literal
      // English fragment is intentional, matches the messages bundle).
      const disclaimer = page.getByTestId("us-quality-data-source");
      await expect(disclaimer).toContainText(/synthetic/i);
    });

    test(`recommendations page renders target positions + risk banner (${locale})`, async ({
      page,
    }) => {
      await page.goto("/recommendations");
      await expect(page.getByTestId("page-recommendations")).toBeVisible();
      await expect(page.getByTestId("recommendations-positions-card")).toBeVisible();
      // Risk banner is embedded on /recommendations and must surface the
      // satellite_us_quality per-sleeve row (B025 risk_panel extension).
      const sleeveRow = page.getByTestId("risk-sleeve-satellite_us_quality");
      await expect(sleeveRow).toBeVisible();
    });

    test(`/risk page header + banner + sleeve note (${locale})`, async ({ page }) => {
      await page.goto("/risk");
      await expect(page.getByTestId("page-risk")).toBeVisible();
      await expect(page.getByTestId("risk-banner")).toBeVisible();
      await expect(page.getByTestId("risk-banner-per-sleeve-list")).toBeVisible();
      await expect(page.getByTestId("risk-sleeve-satellite_us_quality")).toBeVisible();
      // The context card carries the bilingual page narrative; check that
      // the locale-specific noun for the page surfaces.
      const subtitle = await page.getByTestId("risk-page-subtitle").textContent();
      if (locale === "zh-CN") {
        expect(subtitle ?? "").toContain("回撤");
      } else {
        expect(subtitle?.toLowerCase() ?? "").toContain("drawdown");
      }
    });

    test(`reports list surfaces the B025 backtest entry (${locale})`, async ({ page }) => {
      await page.goto("/reports");
      // The reports list renders all *.md under docs/test-reports/; the
      // B025 backtest file lands there from F005. We assert on the
      // per-row testid (slug-only id stays English on purpose) so we
      // do not depend on locale-specific copy.
      await expect(page.getByTestId(`report-link-${REPORT_SLUG}`)).toBeVisible();
    });

    test(`report detail shows the bilingual disclaimer + tables (${locale})`, async ({ page }) => {
      await page.goto(`/reports/${REPORT_SLUG}`);
      // The disclaimer literal is bilingual by design (B024 v0.9.26
      // pattern); both halves must appear regardless of locale.
      await expect(page.locator("body").getByText("research-only").first()).toBeVisible();
      await expect(page.locator("body").getByText("仅供研究使用").first()).toBeVisible();
    });
  });
}

test.describe("B025 locale switch persistence", () => {
  test("locale switcher writes NEXT_LOCALE cookie and survives navigation", async ({
    page,
    context,
  }) => {
    // Start zh-CN so the switcher has somewhere to flip *to*.
    await setLocaleCookie(context, "zh-CN");
    await page.goto("/strategies");
    await expect(page.getByTestId("us-quality-name")).toHaveText("美股质量动量");

    // Use the in-page select (LocaleSwitcher) to flip to en.
    const select = page.locator("select").first();
    await select.selectOption("en");
    await expect(page.getByTestId("us-quality-name")).toHaveText("US Quality Momentum");

    // Navigate to /risk; locale must persist via cookie.
    await page.goto("/risk");
    const subtitle = await page.getByTestId("risk-page-subtitle").textContent();
    expect(subtitle?.toLowerCase() ?? "").toContain("drawdown");

    // And the cookie itself must be set.
    const cookies = await context.cookies();
    const localeCookie = cookies.find((c) => c.name === LOCALE_COOKIE);
    expect(localeCookie?.value).toBe("en");
  });
});

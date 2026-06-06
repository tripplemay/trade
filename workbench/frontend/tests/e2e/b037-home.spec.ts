/**
 * B037 F003 — Daily Journey e2e for the restructured three-section Home.
 *
 * Login (storageState) → Home `/` renders ① NAV + Day P&L hero, ② the
 * reused AI advisor section, ③ the reused market-context card + the
 * sleeve breakdown — with no execution affordance — in both locales.
 *
 * The CI backend has no price_snapshot / advice rows (the timers haven't
 * run), so Day P&L shows "—" and the advisor/market sections show their
 * empty states; the contract under test is "all three sections mount,
 * fetch structured data, no API/console error, no order button".
 */
import { expect, test, type ConsoleMessage, type Response } from "@playwright/test";

const SECTION_TESTIDS = [
  "home-hero",
  "home-nav",
  "home-day-pnl",
  "home-advisor-card",
  "home-market-context-card",
  // B038 F002 — the Home "Today's market news" panel (third section).
  "home-news-card",
  "home-sleeves",
];

test.describe("B037 F003 — Home Daily Journey", () => {
  test("renders all three sections with no execution affordance", async ({ page }) => {
    const apiErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("response", (response: Response) => {
      if (
        response.status() >= 400 &&
        (response.url().includes("/api/home") || response.url().includes("/api/news/latest"))
      ) {
        apiErrors.push(`${response.request().method()} ${response.url()} → ${response.status()}`);
      }
    });
    page.on("console", (msg: ConsoleMessage) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/");

    for (const testId of SECTION_TESTIDS) {
      await expect(page.getByTestId(testId)).toBeVisible();
    }

    // The old quant-dashboard cards are gone (presence→absence, §22).
    await expect(page.getByTestId("dashboard-card-nav")).toHaveCount(0);

    // Research-only: the NAV/Day P&L hero + sleeve breakdown carry no
    // order/execute button (no-execution UI boundary).
    await expect(page.getByTestId("home-hero").getByRole("button")).toHaveCount(0);
    await expect(page.getByTestId("home-sleeves").getByRole("button")).toHaveCount(0);
    // B038 — the news panel is read-only headlines (links only, no order button).
    await expect(page.getByTestId("home-news-card").getByRole("button")).toHaveCount(0);

    expect(apiErrors, `unexpected /home errors: ${apiErrors.join(", ")}`).toEqual([]);
    const appConsoleErrors = consoleErrors.filter(
      (text) => !text.includes("_next/static") && !text.includes("hydrat"),
    );
    expect(appConsoleErrors, `console errors: ${appConsoleErrors.join(", ")}`).toEqual([]);
  });

  for (const { locale, navLabel } of [
    { locale: "en", navLabel: "Net Asset Value" },
    { locale: "zh-CN", navLabel: "净资产" },
  ]) {
    test(`renders the ${locale} hero NAV label`, async ({ page, context }) => {
      await context.addCookies([
        { name: "NEXT_LOCALE", value: locale, domain: "127.0.0.1", path: "/" },
      ]);
      await page.goto("/");
      await expect(page.getByText(navLabel, { exact: true })).toBeVisible();
    });
  }
});

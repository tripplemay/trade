/**
 * B035 F003 — the Home page renders the market-context card from the live
 * backend. The CI backend has no ingested market data (the daily timer
 * hasn't run), but the route always returns the full catalog (6 series
 * with null values), so the card shows its series list with em-dash
 * values — the contract under test is "card mounts, fetches structured
 * data, no API/console error", not specific numbers.
 */
import { expect, test, type ConsoleMessage, type Response } from "@playwright/test";

test.describe("B035 F003 — Home market-context card", () => {
  test("renders the market-context card from /api/market-context", async ({ page }) => {
    const apiErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("response", (response: Response) => {
      if (response.status() >= 400 && response.url().includes("/api/market-context")) {
        apiErrors.push(`${response.request().method()} ${response.url()} → ${response.status()}`);
      }
    });
    page.on("console", (msg: ConsoleMessage) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/");

    const card = page.getByTestId("home-market-context-card");
    await expect(card).toBeVisible();

    // Route returns the full catalog → list renders (values may be em dash).
    await expect(
      page.getByTestId("market-context-list").or(page.getByTestId("market-context-empty")),
    ).toBeVisible();

    expect(apiErrors, `unexpected /market-context errors: ${apiErrors.join(", ")}`).toEqual([]);
    const appConsoleErrors = consoleErrors.filter(
      (text) => !text.includes("_next/static") && !text.includes("hydrat"),
    );
    expect(appConsoleErrors, `console errors: ${appConsoleErrors.join(", ")}`).toEqual([]);
  });
});

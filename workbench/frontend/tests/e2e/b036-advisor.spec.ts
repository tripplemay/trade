/**
 * B036 F003 — the Home page renders the AI Advisor section from the live
 * backend. The CI backend has no precomputed advice (the timer hasn't
 * run), so the section shows its empty state; the contract under test is
 * "section mounts, fetches structured advice, no API/console error" — and
 * that the advisor section never ships an execution button.
 */
import { expect, test, type ConsoleMessage, type Response } from "@playwright/test";

test.describe("B036 F003 — Home AI Advisor section", () => {
  test("renders the advisor section from /api/advisor", async ({ page }) => {
    const apiErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("response", (response: Response) => {
      if (response.status() >= 400 && response.url().includes("/api/advisor")) {
        apiErrors.push(`${response.request().method()} ${response.url()} → ${response.status()}`);
      }
    });
    page.on("console", (msg: ConsoleMessage) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/");

    const card = page.getByTestId("home-advisor-card");
    await expect(card).toBeVisible();

    await expect(
      page.getByTestId("advisor-list").or(page.getByTestId("advisor-empty")),
    ).toBeVisible();

    // Research-only: the advisor section must not ship a trade/execute button.
    await expect(card.getByRole("button")).toHaveCount(0);

    expect(apiErrors, `unexpected /advisor errors: ${apiErrors.join(", ")}`).toEqual([]);
    const appConsoleErrors = consoleErrors.filter(
      (text) => !text.includes("_next/static") && !text.includes("hydrat"),
    );
    expect(appConsoleErrors, `console errors: ${appConsoleErrors.join(", ")}`).toEqual([]);
  });
});

/**
 * B034 F003 — the Recommendations page renders the sleeve NewsPanel with
 * its filter controls, and changing a filter re-queries without surfacing
 * an API/console error. The CI backend has no ingested news (manual
 * ingest only — boundary q), so the panel shows its empty state; the
 * contract under test is "the panel mounts, fetches structured news, and
 * the filters work", not specific news rows.
 */
import { expect, test, type ConsoleMessage, type Response } from "@playwright/test";

test.describe("B034 F003 — sleeve NewsPanel", () => {
  test("renders the news panel + filters and re-queries on filter change", async ({ page }) => {
    const apiErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("response", (response: Response) => {
      const status = response.status();
      const url = response.url();
      if (
        status >= 400 &&
        url.includes("/api/recommendations/news")
      ) {
        apiErrors.push(`${response.request().method()} ${url} → ${status}`);
      }
    });
    page.on("console", (msg: ConsoleMessage) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/recommendations");

    const newsCard = page.getByTestId("recommendations-news-card");
    await expect(newsCard).toBeVisible();

    // Filter controls present.
    await expect(page.getByTestId("news-filter-sleeve")).toBeVisible();
    await expect(page.getByTestId("news-filter-source")).toBeVisible();
    await expect(page.getByTestId("news-filter-topic")).toBeVisible();

    // Panel resolves to either a list or the empty state (CI has no news).
    await expect(
      page.getByTestId("news-list").or(page.getByTestId("news-empty")),
    ).toBeVisible();

    // Changing a filter re-queries; the panel must not error out.
    await page.getByTestId("news-filter-topic").selectOption("财报");
    await expect(
      page.getByTestId("news-list").or(page.getByTestId("news-empty")),
    ).toBeVisible();

    expect(apiErrors, `unexpected /recommendations/news errors: ${apiErrors.join(", ")}`).toEqual([]);
    const appConsoleErrors = consoleErrors.filter(
      (text) => !text.includes("_next/static") && !text.includes("hydrat"),
    );
    expect(appConsoleErrors, `console errors: ${appConsoleErrors.join(", ")}`).toEqual([]);
  });
});

import { expect, test } from "@playwright/test";

test.describe("workbench entry points", () => {
  test("anonymous visit to / redirects to /login and surfaces the disclaimer", async ({ page }) => {
    const response = await page.goto("/");
    // Either middleware-issued 30x or client-side redirect lands the URL at /login.
    await page.waitForURL(/\/login(\?.*)?$/);

    await expect(page.getByTestId("login-page")).toBeVisible();
    await expect(page.getByTestId("login-google-button")).toBeVisible();

    const disclaimer = page.getByTestId("workbench-disclaimer");
    await expect(disclaimer).toBeVisible();
    await expect(disclaimer).toContainText(/research-only/i);

    // We do not assert a specific status code: middleware redirects emit
    // 307/308; following them gives the /login 200. Both paths are
    // acceptable as long as the URL ends at /login.
    if (response) {
      expect(response.url()).toMatch(/\/login(\?.*)?$/);
    }
  });
});

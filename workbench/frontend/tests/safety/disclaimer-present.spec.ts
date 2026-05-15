/**
 * The canonical research-only disclaimer must render on every navigable
 * anonymous route.
 *
 * After B021 F001 the root `/` is gated behind auth; the only anonymously
 * navigable surface is `/login`. Authenticated routes (added in B022) will
 * be covered by a separate Playwright project that signs in first.
 */

import { expect, test } from "@playwright/test";

const NAVIGABLE_ROUTES = ["/login"] as const;

for (const route of NAVIGABLE_ROUTES) {
  test(`disclaimer visible on ${route}`, async ({ page }) => {
    await page.goto(route);
    const disclaimer = page.getByTestId("workbench-disclaimer");
    await expect(disclaimer).toBeVisible();
    await expect(disclaimer).toContainText(/research-only/i);
    await expect(disclaimer).toContainText(/never/i);
  });
}

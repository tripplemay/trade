/**
 * The canonical research-only disclaimer must render on every navigable route.
 *
 * B020 ships a single route (`/`); later batches will append entries to
 * `NAVIGABLE_ROUTES` as they add pages. The disclaimer copy is asserted by
 * substring so future minor wording revisions in `lib/disclaimer.ts` do not
 * need a Playwright update, while the "never authorizes trading" contract
 * stays enforced.
 */

import { expect, test } from "@playwright/test";

const NAVIGABLE_ROUTES = ["/"] as const;

for (const route of NAVIGABLE_ROUTES) {
  test(`disclaimer visible on ${route}`, async ({ page }) => {
    await page.goto(route);
    const disclaimer = page.getByTestId("workbench-disclaimer");
    await expect(disclaimer).toBeVisible();
    await expect(disclaimer).toContainText(/research-only/i);
    await expect(disclaimer).toContainText(/never/i);
  });
}

/**
 * B022 F003 §5 regression: every one of the 7 protected routes renders
 * with the workbench shell intact (TopBar + SideNav + disclaimer Footer)
 * and the SideNav links can be clicked to navigate between them. F006-
 * F012 will replace the page bodies; this test pins the shell contract
 * so a future page can't accidentally hide / move the chrome.
 */
import { expect, test } from "@playwright/test";

import { NAV_ITEMS } from "../../src/components/shell/nav-items";

for (const item of NAV_ITEMS) {
  test(`shell + disclaimer render on ${item.href}`, async ({ page }) => {
    await page.goto(item.href);

    // Auth setup project already injected the session cookie; the
    // request must NOT bounce back to /login.
    await expect(page).toHaveURL(new RegExp(`${item.href === "/" ? "/" : item.href}$`));

    await expect(page.getByTestId("workbench-topbar")).toBeVisible();
    await expect(page.getByTestId("workbench-sidenav")).toBeVisible();

    const disclaimer = page.getByTestId("workbench-disclaimer");
    await expect(disclaimer).toBeVisible();
    await expect(disclaimer).toContainText(/research-only/i);

    // The SideNav link for this page must report itself active (a11y
    // contract: aria-current="page" on the active link). Belt-and-
    // suspenders against a future regression that drops the highlight.
    await expect(page.getByTestId(item.testId)).toHaveAttribute("aria-current", "page");
  });
}

test("Backtest viewer renders ResizablePanel + Run button (B022 F008)", async ({ page }) => {
  await page.goto("/backtest");
  await expect(page.getByTestId("backtest-resizable-group")).toBeVisible();
  await expect(page.getByTestId("backtest-run")).toBeVisible();
  await expect(page.getByTestId("backtest-state")).toHaveText(/idle|running|run /);
});

test("Strategies page renders the list card + export button (B022 F007)", async ({ page }) => {
  await page.goto("/strategies");
  await expect(page.getByTestId("strategies-list-card")).toBeVisible();
  await expect(page.getByTestId("strategies-export-csv")).toBeVisible();
});

test("Home page surfaces the 4 dashboard cards (B022 F006)", async ({ page }) => {
  await page.goto("/");
  // Cards render synchronously with skeleton "—" values; the F006
  // contract says all four are present regardless of whether the
  // /api/dashboard fetch resolves successfully.
  for (const testId of [
    "dashboard-card-nav",
    "dashboard-card-drawdown",
    "dashboard-card-killswitch",
    "dashboard-card-rebalance",
  ]) {
    await expect(page.getByTestId(testId)).toBeVisible();
  }
});

test("clicking each SideNav link navigates without losing the shell", async ({ page }) => {
  // Start at the home route, then walk the nav by clicking each link.
  await page.goto("/");
  for (const item of NAV_ITEMS) {
    await page.getByTestId(item.testId).click();
    await expect(page).toHaveURL(new RegExp(`${item.href === "/" ? "/" : item.href}$`));
    await expect(page.getByTestId("workbench-topbar")).toBeVisible();
    await expect(page.getByTestId("workbench-sidenav")).toBeVisible();
    await expect(page.getByTestId("workbench-disclaimer")).toBeVisible();
  }
});

/**
 * B022 F003 §5 regression: every one of the 7 protected routes renders
 * with the workbench shell intact (TopBar + SideNav + disclaimer Footer)
 * and the SideNav links can be clicked to navigate between them. F006-
 * F012 will replace the page bodies; this test pins the shell contract
 * so a future page can't accidentally hide / move the chrome.
 *
 * B022 F014 fix: each test now collects unexpected API responses
 * (4xx/5xx on `/api/*` paths the page hits) and browser console errors.
 * The prior shell-only assertions hid the dev-server `/api/dashboard
 * 404` etc. that Codex F014 caught — without this guard a fetch failure
 * on a real backend route can still render the skeleton cards and the
 * test passes.
 */
import { expect, test, type ConsoleMessage, type Page, type Response } from "@playwright/test";

import { NAV_ITEMS } from "../../src/components/shell/nav-items";

// /api/auth/* is a NextAuth surface; 401/302 there are normal during the
// initial session probe. Everything else under /api/* is a backend route
// the dev rewrite proxies; 4xx/5xx there is the regression we want to
// catch (e.g. the F009-1 reports 404, the F010-1 runs-dir 500, etc.).
function isMonitoredApiPath(url: string): boolean {
  if (!url.includes("/api/")) return false;
  if (url.includes("/api/auth/")) return false;
  return true;
}

interface PageDiagnostics {
  apiErrors: string[];
  consoleErrors: string[];
}

function attachDiagnostics(page: Page): PageDiagnostics {
  const apiErrors: string[] = [];
  const consoleErrors: string[] = [];

  // 404s under /_next/static/* during the first compile of a dev-mode
  // route are noise: the chunk just hasn't finished writing yet and the
  // browser retries. Treat them as the same kind of dev-only artifact
  // we already filter from the console hook below.
  const isDevModeStaticChunk404 = (url: string, status: number): boolean =>
    status === 404 && (url.includes("/_next/static/") || url.includes("/_next/webpack-hmr"));

  page.on("response", (response: Response) => {
    const status = response.status();
    const url = response.url();
    if (isDevModeStaticChunk404(url, status)) return;
    if (status >= 400 && isMonitoredApiPath(url)) {
      apiErrors.push(`${response.request().method()} ${url} → ${status}`);
    }
  });

  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    // Next.js HMR / dev overlay sometimes logs hydration warnings that
    // depend on render order; filter to messages that look like real
    // application errors. If the filter ever feels too loose, tighten
    // it here instead of dropping the listener.
    if (text.includes("Hydration") || text.includes("react-dom-server")) return;
    // Dev-mode lazy compilation produces transient ``Failed to load
    // resource: ... 404`` lines for /_next/static/* chunks that have not
    // finished writing yet. The browser auto-retries; these are not real
    // application errors. B025 F006 fix-round 2 stopped them from
    // tripping the diagnostics gate in low-resource sandboxes.
    if (text.includes("Failed to load resource") && text.includes("404")) {
      return;
    }
    consoleErrors.push(text);
  });

  page.on("pageerror", (error) => {
    consoleErrors.push(`pageerror: ${error.message}`);
  });

  return { apiErrors, consoleErrors };
}

function assertNoDiagnostics(diag: PageDiagnostics, label: string): void {
  if (diag.apiErrors.length > 0) {
    throw new Error(`${label}: unexpected API errors:\n  - ${diag.apiErrors.join("\n  - ")}`);
  }
  if (diag.consoleErrors.length > 0) {
    throw new Error(
      `${label}: unexpected console errors:\n  - ${diag.consoleErrors.join("\n  - ")}`,
    );
  }
}

for (const item of NAV_ITEMS) {
  test(`shell + disclaimer render on ${item.href}`, async ({ page }) => {
    const diag = attachDiagnostics(page);
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

    // Give in-flight fetches a moment to settle before the diagnostic
    // assertion — most pages issue a single /api/* GET on mount.
    await page.waitForLoadState("networkidle");
    assertNoDiagnostics(diag, `shell render on ${item.href}`);
  });
}

test("Backtest viewer renders ResizablePanel + Run button (B022 F008)", async ({ page }) => {
  const diag = attachDiagnostics(page);
  await page.goto("/backtest");
  await expect(page.getByTestId("backtest-resizable-group")).toBeVisible();
  await expect(page.getByTestId("backtest-run")).toBeVisible();
  await expect(page.getByTestId("backtest-state")).toHaveText(/idle|running|run /);
  await page.waitForLoadState("networkidle");
  assertNoDiagnostics(diag, "Backtest viewer");
});

test("Strategies page renders the list card + export button (B022 F007)", async ({ page }) => {
  const diag = attachDiagnostics(page);
  await page.goto("/strategies");
  await expect(page.getByTestId("strategies-list-card")).toBeVisible();
  await expect(page.getByTestId("strategies-export-csv")).toBeVisible();
  await page.waitForLoadState("networkidle");
  assertNoDiagnostics(diag, "Strategies");
});

test("Home page surfaces the 4 dashboard cards (B022 F006)", async ({ page }) => {
  const diag = attachDiagnostics(page);
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
  await page.waitForLoadState("networkidle");
  assertNoDiagnostics(diag, "Home dashboard");
});

test("clicking each SideNav link navigates without losing the shell", async ({ page }) => {
  // Intentionally NO `attachDiagnostics` here: this test stresses
  // rapid navigation across all 7 routes, so in-flight `/api/*`
  // fetches from the previous page race with the next click and can
  // legitimately surface as non-2xx mid-transition (especially when
  // the dev DB hasn't been migrated). The per-page tests above
  // already cover the API-error monitoring contract; this one
  // narrows its scope to shell + URL navigation.
  await page.goto("/");
  for (const item of NAV_ITEMS) {
    await page.getByTestId(item.testId).click();
    await expect(page).toHaveURL(new RegExp(`${item.href === "/" ? "/" : item.href}$`));
    await expect(page.getByTestId("workbench-topbar")).toBeVisible();
    await expect(page.getByTestId("workbench-sidenav")).toBeVisible();
    await expect(page.getByTestId("workbench-disclaimer")).toBeVisible();
  }
});

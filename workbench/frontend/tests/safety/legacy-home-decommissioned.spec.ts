/**
 * B037 F003 — legacy quant-dashboard Home decommissioning guard
 * (framework v0.9.31 §16 four-place cleanup + evaluator.md §22
 * presence→absence).
 *
 * B037 replaced the old 4-card quant dashboard at `/` with the
 * three-section daily-engagement Home (NAV + Day P&L hero / reused AI
 * advisor / reused market context + sleeve breakdown). This guard fails
 * loudly on any drift back to the old surface across the four places the
 * §16 rule requires a decommission to clean:
 *
 *   1. Route/layout — `(protected)/page.tsx` no longer renders the old
 *      dashboard-card-* testids nor fetches `/api/dashboard`.
 *   2. i18n keys — `home.metrics` / `home.recentReports` /
 *      `home.actionItems` are gone from both message bundles.
 *   3. Components — the old cards were inline in page.tsx (no standalone
 *      component to delete); the new section testids are present instead.
 *   4. E2E — the presence→absence flip lives in
 *      `tests/e2e/protected-routes.spec.ts` (asserts the new testids +
 *      `dashboard-card-nav` count 0).
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

import enMessages from "../../messages/en.json";
import zhCNMessages from "../../messages/zh-CN.json";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const HOME_PAGE = path.join(FRONTEND_ROOT, "src", "app", "(protected)", "page.tsx");

function readFile(p: string): string {
  return fs.readFileSync(p, "utf-8");
}

const OLD_TESTIDS = [
  "dashboard-card-nav",
  "dashboard-card-drawdown",
  "dashboard-card-killswitch",
  "dashboard-card-rebalance",
  "dashboard-state",
  "recent-report",
  "action-item",
];

const OLD_HOME_KEYS = ["metrics", "recentReports", "actionItems"] as const;

describe("B037 F003 — legacy quant-dashboard Home decommissioned", () => {
  it("page.tsx no longer renders any old dashboard-card-* testid", () => {
    const page = readFile(HOME_PAGE);
    for (const testId of OLD_TESTIDS) {
      expect(page.includes(testId)).toBe(false);
    }
  });

  it("page.tsx fetches /api/home, not /api/dashboard", () => {
    const page = readFile(HOME_PAGE);
    expect(page.includes("/api/dashboard")).toBe(false);
    expect(page.includes("/api/home")).toBe(true);
  });

  it("page.tsx renders the three restructured sections", () => {
    const page = readFile(HOME_PAGE);
    for (const testId of ["home-hero", "home-nav", "home-day-pnl", "home-sleeves"]) {
      expect(page.includes(testId)).toBe(true);
    }
  });

  for (const locale of ["en", "zh-CN"] as const) {
    it(`${locale}.json home namespace dropped the old dashboard keys`, () => {
      const raw = readFile(path.join(FRONTEND_ROOT, "messages", `${locale}.json`));
      const bundle = (locale === "en" ? enMessages : zhCNMessages) as {
        home: Record<string, unknown>;
      };
      for (const key of OLD_HOME_KEYS) {
        expect(key in bundle.home).toBe(false);
      }
      // Belt-and-braces on the raw string for the most telltale key.
      expect(raw.includes("\"recentReports\"")).toBe(false);
      expect(raw.includes("\"actionItems\"")).toBe(false);
    });

    it(`${locale}.json home namespace keeps the three new sections`, () => {
      const bundle = (locale === "en" ? enMessages : zhCNMessages) as {
        home: Record<string, unknown>;
      };
      for (const key of ["title", "hero", "sleeves", "marketContext", "advisor"]) {
        expect(key in bundle.home).toBe(true);
      }
    });
  }
});

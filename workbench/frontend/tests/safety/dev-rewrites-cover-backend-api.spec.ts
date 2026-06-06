/**
 * B022 F014-DEV regression: next.config.mjs must rewrite every B022
 * backend `/api/*` route the frontend pages fetch from. The prior
 * config only listed `/api/health` + `/api/protected-test`; Codex
 * F014 caught dev-server 404s for every other page on the Next dev
 * server logs, but the existing Playwright didn't fail because the
 * page tests asserted only shell/card presence.
 *
 * This static check reads next.config.mjs and confirms each backend
 * route prefix appears in the rewrites list. Adding a new backend
 * route requires updating both this list and the config.
 *
 * The matching backend coverage lives in
 * workbench/backend/workbench_api/routes/ — every prefix here MUST
 * have a corresponding router included by workbench_api.app.create_app.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const CONFIG_PATH = join(FRONTEND_ROOT, "next.config.mjs");

const REQUIRED_PREFIXES = [
  "health",
  "protected-test",
  "dashboard",
  "strategies",
  "backtests",
  "reports",
  "recommendations",
  "snapshots",
  "backlog",
  "docs",
  // B023 F002+: the manual-execution workflow surface.
  "execution",
  // B035 F003: the market-context Home card surface.
  "market-context",
  // B036 F003: the AI advisor Home section surface.
  "advisor",
  // B037 F001: the Home NAV + Day P&L + sleeve-breakdown surface.
  "home",
  // B038 F001: the Home "Today's market news" feed (GET /api/news/latest).
  "news",
];

describe("next.config dev rewrites cover all B022 backend prefixes", () => {
  const config = readFileSync(CONFIG_PATH, "utf-8");

  for (const prefix of REQUIRED_PREFIXES) {
    it(`includes the '${prefix}' prefix`, () => {
      expect(config).toContain(`"${prefix}"`);
    });
  }

  it("explicitly excludes /api/auth (NextAuth own routes)", () => {
    // Either no `auth` entry in the proxied list, or — equivalent —
    // the comment block above the list calls out the rule. Both
    // are present in the F014 fix; assert that the literal
    // `/api/auth` string never appears as a destination.
    expect(config).not.toMatch(/destination:.*"\$\{target\}\/api\/auth/);
  });
});

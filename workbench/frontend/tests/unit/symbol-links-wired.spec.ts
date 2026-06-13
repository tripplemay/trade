// @vitest-environment node
/**
 * B060 F001 — site-wide SymbolLink wiring inventory.
 *
 * Every page/component that displays a tradeable security symbol must route it
 * through the shared `<SymbolLink>` so the click-to-quote affordance is
 * consistent site-wide (spec §2). ag-grid cell renderers are mocked in the
 * unit env (DataTable.spec) and the real clickable behaviour is exercised by
 * Codex L2 in a real browser; this static inventory is the unit-time
 * regression anchor that guards against a future edit silently dropping the
 * wiring at any known site.
 */
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(HERE, "..", "..");
const SRC = join(FRONTEND_ROOT, "src");

// The full inventory of symbol-render sites (from the B060 F001 frontend map):
// 3 ag-grid ColDef sites + JSX card/list/table sites across these 9 files.
const WIRED_FILES = [
  "app/(protected)/recommendations/page.tsx", // positions ColDef + wash-sale flags
  "app/(protected)/backtest/page.tsx", // trades ColDef
  "app/(protected)/paper/page.tsx", // per-asset P&L + drift tables
  "app/(protected)/execution/position-diff/page.tsx", // diff ColDef + unmatched list
  "app/(protected)/execution/ticket/page.tsx", // defensive ticker
  "app/(protected)/execution/fills/page.tsx", // preview list + history table
  "components/recommendations/PositionCards.tsx", // card title
  "components/recommendations/NewsPanel.tsx", // matched tickers
  "components/risk/RiskBanner.tsx", // cost-degraded symbols
] as const;

describe("SymbolLink site-wide wiring inventory (B060 F001)", () => {
  it("ships the shared SymbolLink component with the B059 deep link", () => {
    const body = readFileSync(join(SRC, "components", "symbol", "SymbolLink.tsx"), "utf-8");
    expect(body).toContain("/symbols?symbol=");
    expect(body).toContain('useTranslations("symbolLink")');
    expect(body).toContain("toUpperCase()");
  });

  for (const rel of WIRED_FILES) {
    it(`${rel} routes symbols through <SymbolLink>`, () => {
      const body = readFileSync(join(SRC, ...rel.split("/")), "utf-8");
      expect(body).toContain("@/components/symbol/SymbolLink");
      expect(body).toContain("<SymbolLink");
    });
  }
});

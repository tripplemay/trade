// @vitest-environment happy-dom
/**
 * B056 F003 — 模拟盘 page renders the six sections from /api/paper/*, with the
 * "simulated, not real money" badge, the active summary (incl. vs-SPY), the
 * per-asset P&L table (+ cash row), allocation drift, and the simplified
 * rebalance log; plus the inactive activation path. NAV curve uses the empty
 * state here so the reused (separately tested) chart isn't mounted in jsdom.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import PaperPage from "@/app/(protected)/paper/page";

type PaperView = components["schemas"]["PaperView"];

const STRATEGIES = {
  strategies: [
    { strategy_id: "master_portfolio", name: "旗舰组合", has_account: true },
  ],
};

const ACTIVE_VIEW: PaperView = {
  active: true,
  strategy_id: "master_portfolio",
  strategy_name: "旗舰组合",
  cash: 0.1,
  summary: {
    strategy_id: "master_portfolio",
    base_currency: "USD",
    initial_capital: 100000,
    activated_on: "2026-06-12",
    days_running: 3,
    current_nav: 105000,
    total_pnl: 5000,
    total_pnl_pct: 0.05,
    today_pnl: 250,
    benchmark_pnl_pct: 0.03,
    vs_benchmark_pct: 0.02,
    next_rebalance: "2026-06-30",
    fee_bps: 5,
    slippage_bps: 5,
  },
  nav_curve: [], // empty → curveEmpty text, no chart mount
  positions: [
    {
      symbol: "AAA", shares: 599.4, avg_cost: 100, close: 110, market_value: 65934,
      weight: 0.62, unrealized_pnl: 5994, unrealized_pnl_pct: 0.1,
    },
    {
      symbol: "BBB", shares: 799.2, avg_cost: 50, close: 50, market_value: 39960,
      weight: 0.38, unrealized_pnl: 0, unrealized_pnl_pct: 0,
    },
  ],
  drift: [
    { symbol: "AAA", current_weight: 0.62, target_weight: 0.6, drift: 0.02 },
    { symbol: "BBB", current_weight: 0.38, target_weight: 0.4, drift: -0.02 },
  ],
  rebalances: [
    { date: "2026-06-12", cost: 99.9, cumulative_cost: 99.9 },
  ],
};

function mockFetch(routes: Record<string, unknown>): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url ?? String(input);
    const key = Object.keys(routes).find((k) => url.includes(k));
    return new Response(JSON.stringify(key ? routes[key] : {}), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PaperPage (B056 F003)", () => {
  it("renders the six sections of an active paper account in Chinese", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/paper/strategies": STRATEGIES,
        "/api/paper/master_portfolio": ACTIVE_VIEW,
      }),
    );
    const { getByTestId, getAllByTestId } = renderWithIntl(<PaperPage />, { locale: "zh-CN" });

    await waitFor(() => expect(getByTestId("paper-summary")).toBeInTheDocument());
    // "simulated, not real" badge always present.
    expect(getByTestId("paper-simulated-badge").textContent).toContain("模拟盘");
    // ③ per-asset table: two position rows + a cash row.
    expect(getAllByTestId("paper-position-row")).toHaveLength(2);
    expect(getByTestId("paper-cash-row")).toBeInTheDocument();
    // ④ drift + ⑤ rebalance log.
    expect(getAllByTestId("paper-drift-row")).toHaveLength(2);
    expect(getAllByTestId("paper-rebalance-row")).toHaveLength(1);
    // vs-SPY outperformance shown.
    expect(getByTestId("paper-vs-benchmark").textContent).toContain("跑赢");
    // ② empty-curve forward state (no chart mounted).
    expect(getByTestId("paper-nav-curve").textContent).toContain("前向累积中");
  });

  it("shows the activation form when inactive", async () => {
    const inactive: PaperView = {
      active: false,
      strategy_id: "master_portfolio",
      strategy_name: "旗舰组合",
      cash: 0,
      nav_curve: [],
      positions: [],
      drift: [],
      rebalances: [],
      summary: null,
    };
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/paper/strategies": {
          strategies: [
            { strategy_id: "master_portfolio", name: "旗舰组合", has_account: false },
          ],
        },
        "/api/paper/master_portfolio": inactive,
      }),
    );
    const { getByTestId } = renderWithIntl(<PaperPage />, { locale: "zh-CN" });
    await waitFor(() => expect(getByTestId("paper-inactive")).toBeInTheDocument());
    expect(getByTestId("paper-activate")).toBeInTheDocument();
    // The activation button is clickable (kicks off the POST).
    fireEvent.click(getByTestId("paper-activate"));
  });
});

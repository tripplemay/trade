// @vitest-environment happy-dom
/**
 * B058 F005 — Paper page "对齐当前目标" (align to current target) button: a
 * synchronous POST that aligns the paper book to the current target, then shows
 * the result (positions / skipped-symbols hint / no-target / error).
 *
 * The chart wrapper is mocked at module scope; we focus on the button wiring.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

vi.mock("@/components/chart", () => ({
  EquityCurveChart: () => null,
}));

import PaperPage from "@/app/(protected)/paper/page";

const STRATEGIES: components["schemas"]["PaperStrategiesResponse"] = {
  strategies: [
    { strategy_id: "master_portfolio", name: "旗舰组合", has_account: true },
  ],
};

const ACTIVE_VIEW: components["schemas"]["PaperView"] = {
  active: true,
  strategy_id: "master_portfolio",
  strategy_name: "旗舰组合",
  summary: {
    strategy_id: "master_portfolio",
    base_currency: "USD",
    initial_capital: 100000,
    activated_on: "2026-06-01",
    days_running: 11,
    current_nav: 100500,
    total_pnl: 500,
    total_pnl_pct: 0.005,
    today_pnl: 50,
    benchmark_pnl_pct: 0.004,
    vs_benchmark_pct: 0.001,
    next_rebalance: "2026-06-30",
    fee_bps: 5,
    slippage_bps: 5,
  },
  cash: 100,
  nav_curve: [],
  positions: [],
  drift: [],
  rebalances: [],
};

const REBAL_OK: components["schemas"]["RebalanceNowResponse"] = {
  strategy_id: "master_portfolio",
  has_target: true,
  rebalanced: true,
  positions: 4,
  build_complete: true,
  skipped_symbols: [],
};

function buildFetch(map: Record<string, unknown>): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? input.toString());
    const path = url.split("?")[0] ?? url;
    const body = map[path] ?? map[url];
    if (body === undefined) return new Response("not-found", { status: 404 });
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PaperPage rebalance-now (B058 F005)", () => {
  it("renders the align button on an active account", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/paper/strategies": STRATEGIES,
        "/api/paper/master_portfolio": ACTIVE_VIEW,
      }),
    );
    const { getByTestId } = renderWithIntl(<PaperPage />);
    await waitFor(() => {
      expect(getByTestId("paper-rebalance-now")).toBeInTheDocument();
    });
  });

  it("align button POSTs rebalance-now and surfaces the aligned result", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/paper/strategies": STRATEGIES,
        "/api/paper/master_portfolio": ACTIVE_VIEW,
        "/api/paper/master_portfolio/rebalance-now": REBAL_OK,
      }),
    );
    const { getByTestId } = renderWithIntl(<PaperPage />);
    await waitFor(() => expect(getByTestId("paper-rebalance-now")).not.toBeDisabled());
    fireEvent.click(getByTestId("paper-rebalance-now"));
    await waitFor(() => {
      expect(getByTestId("paper-align-result")).toBeInTheDocument();
    });
  });

  it("align surfaces the skipped_symbols 'missing mark' hint honestly", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/paper/strategies": STRATEGIES,
        "/api/paper/master_portfolio": ACTIVE_VIEW,
        "/api/paper/master_portfolio/rebalance-now": {
          ...REBAL_OK,
          build_complete: false,
          skipped_symbols: ["QQQ", "TLT"],
        },
      }),
    );
    const { getByTestId } = renderWithIntl(<PaperPage />);
    await waitFor(() => expect(getByTestId("paper-rebalance-now")).not.toBeDisabled());
    fireEvent.click(getByTestId("paper-rebalance-now"));
    await waitFor(() => {
      expect(getByTestId("paper-align-skipped")).toHaveTextContent(/QQQ/);
    });
  });

  it("align shows the no-target hint when there is no target to align to", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/paper/strategies": STRATEGIES,
        "/api/paper/master_portfolio": ACTIVE_VIEW,
        "/api/paper/master_portfolio/rebalance-now": {
          strategy_id: "master_portfolio",
          has_target: false,
          rebalanced: false,
          positions: 0,
          build_complete: false,
          skipped_symbols: [],
        },
      }),
    );
    const { getByTestId } = renderWithIntl(<PaperPage />);
    await waitFor(() => expect(getByTestId("paper-rebalance-now")).not.toBeDisabled());
    fireEvent.click(getByTestId("paper-rebalance-now"));
    await waitFor(() => {
      expect(getByTestId("paper-align-no-target")).toBeInTheDocument();
    });
  });
});

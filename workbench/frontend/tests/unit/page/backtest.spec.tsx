// @vitest-environment happy-dom
/**
 * B022 F008 — Backtest viewer page renders the ResizablePanel split,
 * pulls the strategy list, runs a backtest on click, and surfaces the
 * synthetic result through metrics + trades + state line.
 *
 * AG Grid + chart wrappers + Radix Select + react-resizable-panels are
 * all mocked at module scope; the test focuses on page wiring (form
 * state ↔ fetch ↔ result state) rather than the underlying widgets
 * (which are exercised in F004 / F005).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

vi.mock("ag-grid-react", () => ({ AgGridReact: () => null }));
vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: vi.fn() },
  themeQuartz: { withPart: () => ({}) },
  colorSchemeDark: {},
}));
vi.mock("lightweight-charts", () => ({
  AreaSeries: {},
  HistogramSeries: {},
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn(), applyOptions: vi.fn() }),
    removeSeries: vi.fn(),
    remove: vi.fn(),
    takeScreenshot: () => ({ toBlob: (cb: (b: Blob | null) => void) => cb(null) }),
    timeScale: () => ({
      subscribeVisibleTimeRangeChange: vi.fn(),
      unsubscribeVisibleTimeRangeChange: vi.fn(),
      setVisibleRange: vi.fn(),
    }),
  }),
}));
vi.mock("echarts-for-react", () => ({ default: () => null }));
// Radix Select breaks under happy-dom without scrollIntoView; bypass
// to a plain native element since the form interactions in this test
// only need value/onChange. Drop the visual surface entirely.
vi.mock("@/components/ui/select", () => ({
  Select: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectTrigger: ({ children, ...rest }: { children: React.ReactNode }) => (
    <button {...rest}>{children}</button>
  ),
  SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectItem: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectValue: ({ placeholder }: { placeholder?: string }) => (
    <span>{placeholder ?? ""}</span>
  ),
}));

import BacktestPage from "@/app/(protected)/backtest/page";

const STRATEGY_LIST: components["schemas"]["StrategyListResponse"] = {
  strategies: [
    {
      id: "B013-regime-quarterly",
      name: "Regime-Adaptive Multi-Asset (quarterly)",
      sleeve: "regime",
      status: "active",
      last_sweep_date: "2026-05-13",
    },
  ],
};

const RUN_RESULT: components["schemas"]["BacktestRunResponse"] = {
  run_id: "abc123",
  status: "ok",
  metrics: {
    cagr: 0.085,
    sharpe: 1.42,
    sortino: 1.71,
    max_drawdown: -0.063,
    turnover: 0.42,
    win_rate: 0.55,
  },
  equity: [
    { date: "2024-01-01", nav: 100, benchmark_spy: 100, benchmark_6040: 100 },
    { date: "2024-06-30", nav: 104.5, benchmark_spy: 102.2, benchmark_6040: 101.1 },
  ],
  allocations: [{ date: "2024-01-01", weights: { VTI: 0.5, BND: 0.3, GLD: 0.2 } }],
  trades: [
    {
      date: "2024-01-01",
      symbol: "VTI",
      side: "buy",
      quantity: 50,
      price: 220,
      notional: 11000,
    },
  ],
};

function buildFetch(map: Record<string, unknown>): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url ?? input.toString();
    const body = map[url];
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

describe("BacktestPage (B022 F008)", () => {
  it("renders the ResizablePanel scaffold + state line idle", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/strategies": STRATEGY_LIST }));
    const { getByTestId } = renderWithIntl(<BacktestPage />);
    expect(getByTestId("page-backtest")).toBeInTheDocument();
    expect(getByTestId("backtest-resizable-group")).toBeInTheDocument();
    await waitFor(() => {
      expect(getByTestId("backtest-state")).toHaveTextContent(/idle/);
    });
  });

  it("clicks Run → posts to /api/backtests/run → surfaces metrics + state line", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/strategies": STRATEGY_LIST,
        "/api/backtests/run": RUN_RESULT,
      }),
    );
    const { getByTestId } = renderWithIntl(<BacktestPage />);
    // Wait for the strategy list to land so the Run button is enabled.
    await waitFor(() => {
      expect(getByTestId("backtest-run")).not.toBeDisabled();
    });
    fireEvent.click(getByTestId("backtest-run"));
    await waitFor(() => {
      expect(getByTestId("backtest-state")).toHaveTextContent(/run abc123/);
    });
    // Headline metrics populated from RUN_RESULT.
    const metricsCard = getByTestId("backtest-metrics");
    expect(metricsCard).toHaveTextContent(/8\.50%/); // cagr 0.085
    expect(metricsCard).toHaveTextContent(/1\.42/); // sharpe
  });

  it("comparison toggle controls whether SPY + 60/40 layers ship", async () => {
    // Toggle behaviour is internal state — assert via the rendered control
    // since the chart wrapper is mocked. Default-on per F008 acceptance.
    vi.stubGlobal("fetch", buildFetch({ "/api/strategies": STRATEGY_LIST }));
    const { getByTestId } = renderWithIntl(<BacktestPage />);
    const toggle = getByTestId("backtest-comparison-toggle") as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.checked).toBe(false);
  });

  it("surfaces a fetch error in the state line", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/strategies": STRATEGY_LIST,
      }),
    );
    const { getByTestId } = renderWithIntl(<BacktestPage />);
    await waitFor(() => {
      expect(getByTestId("backtest-run")).not.toBeDisabled();
    });
    fireEvent.click(getByTestId("backtest-run"));
    await waitFor(() => {
      expect(getByTestId("backtest-state")).toHaveTextContent(/error/);
    });
  });
});

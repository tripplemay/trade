// @vitest-environment happy-dom
/**
 * B022 F007 — Strategies page renders the list + per-strategy detail
 * panel and resolves spec/code provenance into /docs/{path} buttons.
 *
 * Chart libraries and AG Grid are mocked at module scope so the test
 * focuses on the page-level wiring (list state ↔ detail fetch ↔ deep
 * link) rather than the wrappers covered separately in F004 / F005.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

// Mock next/navigation's useSearchParams BEFORE importing the page so
// the page's import-time hook resolution picks up the stubbed value.
const searchParamsValue: URLSearchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsValue,
}));

vi.mock("ag-grid-react", () => ({
  AgGridReact: () => null,
}));
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
vi.mock("echarts-for-react", () => ({
  default: () => null,
}));

import StrategiesPage from "@/app/(protected)/strategies/page";

const LIST: components["schemas"]["StrategyListResponse"] = {
  strategies: [
    {
      id: "B013-regime-quarterly",
      name: "Regime-Adaptive Multi-Asset (quarterly)",
      sleeve: "regime",
      status: "active",
      last_sweep_date: "2026-05-13",
    },
    {
      id: "B016-risk-parity-hrp",
      name: "Risk Parity HRP",
      sleeve: "risk_parity",
      status: "active",
      last_sweep_date: null,
    },
  ],
};

const DETAIL: components["schemas"]["StrategyDetail"] = {
  id: "B013-regime-quarterly",
  name: "Regime-Adaptive Multi-Asset (quarterly)",
  sleeve: "regime",
  status: "active",
  last_sweep_date: "2026-05-13",
  config: { rebalance: "quarterly", activation_threshold: 0.11 },
  provenance: {
    spec_path: "docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md",
    code_path: "trade/strategies/regime_adaptive",
    last_sweep_path: "docs/test-reports/B019-retune-recommendations-signoff-2026-05-15.md",
  },
  equity_curve: [],
  drawdown_series: [],
  turnover_heatmap: [],
};

function buildFetch(map: Record<string, unknown>): typeof fetch {
  return vi.fn(async (input: Request | string | URL) => {
    const url = typeof input === "string" ? input : input.toString();
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
  // Reset the URLSearchParams stub between cases.
  for (const key of Array.from(searchParamsValue.keys())) {
    searchParamsValue.delete(key);
  }
});

describe("StrategiesPage (B022 F007)", () => {
  it("renders the list shell + state-line count once the list resolves", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/strategies": LIST,
        "/api/strategies/B013-regime-quarterly": DETAIL,
      }),
    );
    const { getByTestId } = renderWithIntl(<StrategiesPage />);
    expect(getByTestId("page-strategies")).toBeInTheDocument();
    expect(getByTestId("strategies-list-card")).toBeInTheDocument();
    await waitFor(() => {
      expect(getByTestId("strategies-state")).toHaveTextContent(/2 sleeves/);
    });
  });

  it("auto-selects the first strategy and renders the detail panel", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/strategies": LIST,
        "/api/strategies/B013-regime-quarterly": DETAIL,
      }),
    );
    const { getByTestId } = renderWithIntl(<StrategiesPage />);
    await waitFor(() => {
      expect(getByTestId("strategy-detail")).toBeInTheDocument();
    });
    // Spec/code/sweep buttons resolve to /docs/{path}. With shadcn's
    // asChild + next/link, the data-testid lives on the rendered <a>
    // directly (Slot collapses the Button wrapper).
    const specLink = getByTestId("strategy-detail-spec-link");
    expect(specLink).toHaveAttribute(
      "href",
      "/docs/docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md",
    );
  });

  it("honours ?selected to deep-link a non-default strategy", async () => {
    searchParamsValue.set("selected", "B016-risk-parity-hrp");
    const altDetail: components["schemas"]["StrategyDetail"] = {
      ...DETAIL,
      id: "B016-risk-parity-hrp",
      name: "Risk Parity HRP",
      sleeve: "risk_parity",
      config: {},
      provenance: {
        spec_path: "docs/specs/B016-risk-parity-hrp-upgrade-spec.md",
        code_path: "trade/strategies/risk_parity_hrp.py",
        last_sweep_path: null,
      },
    };
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/strategies": LIST,
        "/api/strategies/B016-risk-parity-hrp": altDetail,
      }),
    );
    const { getByTestId } = renderWithIntl(<StrategiesPage />);
    await waitFor(() => {
      expect(getByTestId("strategy-detail")).toHaveTextContent("Risk Parity HRP");
      expect(getByTestId("strategy-detail-sweep-link-empty")).toBeInTheDocument();
    });
  });

  it("surfaces a fetch failure in the state line without crashing the list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 500 })) as unknown as typeof fetch,
    );
    const { getByTestId } = renderWithIntl(<StrategiesPage />);
    await waitFor(() => {
      expect(getByTestId("strategies-state")).toHaveTextContent(/unreachable/);
    });
  });
});

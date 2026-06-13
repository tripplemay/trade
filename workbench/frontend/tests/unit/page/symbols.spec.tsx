// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";
import type { components } from "@/types/api";

// next/navigation has no App Router context in jsdom — mock the hooks the
// symbols page uses. `nav.search` is mutated per test to drive the initial
// ?symbol= query param.
const nav = vi.hoisted(() => ({ search: "", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: nav.replace, push: nav.replace, prefetch: vi.fn() }),
  usePathname: () => "/symbols",
}));

// lightweight-charts can't render in happy-dom — mock the chart component.
vi.mock("@/components/chart/PriceChart", () => ({
  default: () => <div data-testid="price-chart-mock" />,
}));

import SymbolsPage from "@/app/(protected)/symbols/page";

const DETAIL: components["schemas"]["SymbolPriceDetail"] = {
  symbol: "AAPL",
  as_of: "2026-06-12",
  close: 150.25,
  source: "yfinance",
  is_eod: true,
  week52_high: 200.0,
  week52_low: 90.0,
  returns: {
    one_month: 0.05,
    three_month: -0.02,
    six_month: 0.1,
    one_year: 0.2,
    ytd: 0.15,
  },
  bars: [
    { obs_date: "2026-06-10", open: 148, high: 151, low: 147, close: 149.5, volume: 100 },
    { obs_date: "2026-06-12", open: 149.5, high: 152, low: 149, close: 150.25, volume: 200 },
  ],
};

function stubFetch(status: number, body: unknown): ReturnType<typeof vi.fn> {
  const fn = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  nav.search = "";
  nav.replace = vi.fn();
});

describe("SymbolsPage", () => {
  it("shows the search box + research disclaimer + empty prompt before any lookup", () => {
    nav.search = "";
    const fetchSpy = stubFetch(200, DETAIL);
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    expect(getByTestId("symbols-search-input")).toBeInTheDocument();
    expect(getByTestId("symbols-search-button")).toBeInTheDocument();
    expect(getByTestId("symbols-disclaimer-card")).toBeInTheDocument();
    expect(getByTestId("symbols-empty-prompt")).toBeInTheDocument();
    // No symbol → no external fetch.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renders EOD price detail (close + source + 52w + returns + chart) for a found symbol", async () => {
    nav.search = "symbol=AAPL";
    stubFetch(200, DETAIL);
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    await waitFor(() => expect(getByTestId("symbols-detail")).toBeInTheDocument());
    expect(getByTestId("symbols-close")).toHaveTextContent("150.25");
    // Honest EOD/source labelling present.
    expect(getByTestId("symbols-source-badge")).toHaveTextContent(/yfinance/);
    expect(getByTestId("symbols-eod-note")).toHaveTextContent("2026-06-12");
    expect(getByTestId("symbols-week52-high")).toHaveTextContent("200.00");
    expect(getByTestId("symbols-week52-low")).toHaveTextContent("90.00");
    expect(getByTestId("symbols-returns")).toHaveTextContent("+5.00%");
    expect(getByTestId("symbols-returns")).toHaveTextContent("-2.00%");
    expect(getByTestId("price-chart-mock")).toBeInTheDocument();
  });

  it("shows the backend's actionable error message for an unknown ticker", async () => {
    nav.search = "symbol=ZZZZ";
    stubFetch(404, { detail: "No price data for ZZZZ. Check the symbol, e.g. AAPL, SPY." });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    await waitFor(() => expect(getByTestId("symbols-error")).toBeInTheDocument());
    expect(getByTestId("symbols-error")).toHaveTextContent(/No price data for ZZZZ/);
  });

  it("exposes no buy/sell/execute button (research-only surface)", async () => {
    nav.search = "symbol=AAPL";
    stubFetch(200, DETAIL);
    const { getByTestId, container } = renderWithIntl(<SymbolsPage />);
    await waitFor(() => expect(getByTestId("symbols-detail")).toBeInTheDocument());
    // The honest disclaimer prose legitimately says "no buy/sell"; the real
    // guard is that no clickable button is an order/execute action.
    const buttonLabels = Array.from(container.querySelectorAll("button")).map(
      (b) => b.textContent ?? "",
    );
    for (const label of buttonLabels) {
      expect(label).not.toMatch(/execute|place order|buy|sell|下单|买入|卖出|实盘/i);
    }
  });

  it("submitting the search box triggers a lookup and updates the URL", async () => {
    nav.search = "";
    stubFetch(200, DETAIL);
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    fireEvent.change(getByTestId("symbols-search-input"), { target: { value: "aapl" } });
    fireEvent.click(getByTestId("symbols-search-button"));

    await waitFor(() => expect(getByTestId("symbols-detail")).toBeInTheDocument());
    expect(nav.replace).toHaveBeenCalledWith("/symbols?symbol=AAPL");
  });
});

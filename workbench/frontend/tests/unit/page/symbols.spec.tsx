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
  currency: "USD",
  is_eod: true,
  week52_high: 200.0,
  week52_low: 90.0,
  returns: { one_month: 0.05, three_month: -0.02, six_month: 0.1, one_year: 0.2, ytd: 0.15 },
  bars: [
    { obs_date: "2026-06-10", open: 148, high: 151, low: 147, close: 149.5, volume: 100 },
    { obs_date: "2026-06-12", open: 149.5, high: 152, low: 149, close: 150.25, volume: 200 },
  ],
};

const DETAIL_CN: components["schemas"]["SymbolPriceDetail"] = {
  symbol: "600519.SH",
  as_of: "2026-06-12",
  close: 1630.0,
  source: "akshare",
  currency: "CNY",
  is_eod: true,
  week52_high: 1800.0,
  week52_low: 1500.0,
  returns: { one_month: 0.03, three_month: 0.01, six_month: -0.05, one_year: 0.1, ytd: 0.08 },
  bars: [
    { obs_date: "2026-06-11", open: 1620, high: 1635, low: 1615, close: 1625, volume: 100 },
    { obs_date: "2026-06-12", open: 1625, high: 1640, low: 1620, close: 1630, volume: 200 },
  ],
};

const FUND_US: components["schemas"]["SymbolFundamentals"] = {
  symbol: "AAPL",
  source: "yfinance",
  available: true,
  reason: null,
  is_us_equity: true,
  name: "Apple Inc.",
  sector: "Technology",
  industry: "Consumer Electronics",
  currency: "USD",
  quote_type: "EQUITY",
  country: "United States",
  market_cap: 3.0e12,
  trailing_pe: 30.5,
  forward_pe: 28.0,
  price_to_book: 45.0,
  dividend_yield: 0.005,
  profit_margins: 0.25,
  gross_margins: 0.44,
  revenue: 4.0e11,
  shares_outstanding: 1.5e10,
  return_on_equity: 1.5,
  debt_to_equity: 150.0,
};

const FUND_NON_US: components["schemas"]["SymbolFundamentals"] = {
  ...FUND_US,
  available: false,
  reason: "non_us",
  is_us_equity: false,
  name: null,
  sector: null,
  industry: null,
  currency: "HKD",
  country: "China",
  market_cap: null,
  trailing_pe: null,
  forward_pe: null,
  price_to_book: null,
  dividend_yield: null,
  profit_margins: null,
  gross_margins: null,
  revenue: null,
  shares_outstanding: null,
  return_on_equity: null,
  debt_to_equity: null,
};

const FUND_CN: components["schemas"]["SymbolFundamentals"] = {
  symbol: "600519.SH",
  source: "akshare",
  available: true,
  reason: null,
  is_us_equity: false,
  accounting_standard: "CAS",
  as_of: "2026-03-31",
  name: null,
  sector: null,
  industry: null,
  currency: "CNY",
  quote_type: "EQUITY",
  country: "China",
  market_cap: 1.55e12,
  trailing_pe: 18.74,
  forward_pe: null,
  price_to_book: 5.72,
  dividend_yield: null,
  profit_margins: 0.5222,
  gross_margins: 0.8976,
  revenue: 5.47e10,
  shares_outstanding: 1.25e9,
  return_on_equity: 0.1057,
  debt_to_equity: 14.32,
  eps: 21.76,
  book_value_per_share: 216.32,
  net_income: 2.72e10,
  debt_to_asset: 12.12,
};

type RouteSpec = { status: number; body: unknown };

const NEWS_ONE: components["schemas"]["SymbolNewsResponse"] = {
  symbol: "AAPL",
  items: [
    {
      news_id: "n1",
      title: "苹果最新头条",
      source: "yahoo_rss",
      url: "https://example.com/n1",
      published_at: "2026-06-12T12:00:00+00:00",
      topics: ["财报"],
    },
  ],
};

const NEWS_EMPTY: components["schemas"]["SymbolNewsResponse"] = { symbol: "AAPL", items: [] };

function buildFetch(opts: {
  price?: RouteSpec;
  fundamentals?: RouteSpec;
  news?: RouteSpec;
}): ReturnType<typeof vi.fn> {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    let which: RouteSpec | undefined;
    if (url.includes("/fundamentals")) which = opts.fundamentals;
    else if (url.includes("/news")) which = opts.news;
    else which = opts.price;
    if (!which) return new Response("not-found", { status: 404 });
    return new Response(JSON.stringify(which.body), {
      status: which.status,
      headers: { "content-type": "application/json" },
    });
  });
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
    const fetchSpy = buildFetch({ price: { status: 200, body: DETAIL } });
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
    buildFetch({
      price: { status: 200, body: DETAIL },
      fundamentals: { status: 200, body: FUND_US },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    await waitFor(() => expect(getByTestId("symbols-detail")).toBeInTheDocument());
    expect(getByTestId("symbols-close")).toHaveTextContent("150.25");
    // B061 F004 — US price is currency-formatted ($) + explicit USD badge.
    expect(getByTestId("symbols-close")).toHaveTextContent("$");
    expect(getByTestId("symbols-currency-badge")).toHaveTextContent("USD");
    // Honest EOD/source labelling present.
    expect(getByTestId("symbols-source-badge")).toHaveTextContent(/yfinance/);
    expect(getByTestId("symbols-eod-note")).toHaveTextContent("2026-06-12");
    expect(getByTestId("symbols-week52-high")).toHaveTextContent("200.00");
    expect(getByTestId("symbols-week52-low")).toHaveTextContent("90.00");
    expect(getByTestId("symbols-returns")).toHaveTextContent("+5.00%");
    expect(getByTestId("symbols-returns")).toHaveTextContent("-2.00%");
    expect(getByTestId("price-chart-mock")).toBeInTheDocument();
  });

  it("renders an A-share (CN) lookup with CNY currency + honest akshare source", async () => {
    nav.search = "symbol=600519.SH";
    buildFetch({
      price: { status: 200, body: DETAIL_CN },
      fundamentals: { status: 200, body: FUND_NON_US },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    await waitFor(() => expect(getByTestId("symbols-detail")).toBeInTheDocument());
    // Currency-aware: ¥ on the price, explicit CNY badge, honest akshare source.
    expect(getByTestId("symbols-close")).toHaveTextContent("¥");
    expect(getByTestId("symbols-close")).toHaveTextContent("1,630.00");
    expect(getByTestId("symbols-currency-badge")).toHaveTextContent("CNY");
    expect(getByTestId("symbols-source-badge")).toHaveTextContent(/akshare/);
    expect(getByTestId("symbols-week52-high")).toHaveTextContent("¥");
  });

  it("renders fundamentals (market cap etc.) for a US equity", async () => {
    nav.search = "symbol=AAPL";
    buildFetch({
      price: { status: 200, body: DETAIL },
      fundamentals: { status: 200, body: FUND_US },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    await waitFor(() => expect(getByTestId("symbols-fundamentals")).toHaveTextContent("3T"));
  });

  it("degrades fundamentals honestly for a non-US ticker (US-only)", async () => {
    nav.search = "symbol=AAPL";
    buildFetch({
      price: { status: 200, body: DETAIL },
      fundamentals: { status: 200, body: FUND_NON_US },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    await waitFor(() =>
      expect(getByTestId("symbols-fundamentals-unavailable")).toBeInTheDocument(),
    );
  });

  it("renders A-share fundamentals with CAS standard + ¥ market cap + EPS (B064)", async () => {
    nav.search = "symbol=600519.SH";
    buildFetch({
      price: { status: 200, body: DETAIL_CN },
      fundamentals: { status: 200, body: FUND_CN },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    // Wait for the standard note itself (the fundamentals card renders during
    // loading too, so waiting on the card would race the fetch).
    await waitFor(() => expect(getByTestId("symbols-fundamentals-standard")).toBeInTheDocument());
    const standard = getByTestId("symbols-fundamentals-standard");
    expect(standard).toHaveTextContent("CAS");
    expect(standard).toHaveTextContent("2026-03-31"); // reporting period
    const fund = getByTestId("symbols-fundamentals");
    expect(fund).toHaveTextContent("¥"); // currency-aware market cap (CNY)
    expect(fund).toHaveTextContent("1.55T"); // compact market cap
    expect(fund).toHaveTextContent("21.76"); // EPS (CAS extra)
    expect(fund).toHaveTextContent("12.12%"); // debt/assets percent points
  });

  it("renders HK fundamentals with HK$ on market cap AND EPS (no USD-ambiguous $)", async () => {
    nav.search = "symbol=0700.HK";
    const FUND_HK: components["schemas"]["SymbolFundamentals"] = {
      ...FUND_CN,
      symbol: "0700.HK",
      accounting_standard: "HKFRS",
      as_of: "2025-12-31",
      name: "腾讯控股",
      currency: "HKD",
      country: "Hong Kong",
      market_cap: 4.06e12,
      eps: 24.749,
      book_value_per_share: 126.72,
      debt_to_equity: null, // HK source has none
    };
    buildFetch({
      price: { status: 200, body: { ...DETAIL_CN, symbol: "0700.HK", currency: "HKD" } },
      fundamentals: { status: 200, body: FUND_HK },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    await waitFor(() => expect(getByTestId("symbols-fundamentals-standard")).toBeInTheDocument());
    const fund = getByTestId("symbols-fundamentals");
    expect(fund).toHaveTextContent("HK$4.06T"); // market cap
    expect(fund).toHaveTextContent("HK$24.75"); // EPS — HK$, NOT a bare $
    expect(getByTestId("symbols-fundamentals-name")).toHaveTextContent("腾讯控股");
    expect(getByTestId("symbols-fundamentals-standard")).toHaveTextContent("HKFRS");
  });

  it("degrades CN fundamentals honestly when the akshare source is unreachable (B064)", async () => {
    nav.search = "symbol=600519.SH";
    const unreachable: components["schemas"]["SymbolFundamentals"] = {
      ...FUND_CN,
      available: false,
      reason: "source_unavailable",
      market_cap: null,
      trailing_pe: null,
      eps: null,
    };
    buildFetch({
      price: { status: 200, body: DETAIL_CN },
      fundamentals: { status: 200, body: unreachable },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    await waitFor(() =>
      expect(getByTestId("symbols-fundamentals-unavailable")).toBeInTheDocument(),
    );
  });

  it("renders recent news headlines for a symbol", async () => {
    nav.search = "symbol=AAPL";
    buildFetch({ price: { status: 200, body: DETAIL }, news: { status: 200, body: NEWS_ONE } });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    await waitFor(() => expect(getByTestId("symbols-news")).toHaveTextContent("苹果最新头条"));
  });

  it("shows an honest empty state when a symbol has no news", async () => {
    nav.search = "symbol=AAPL";
    buildFetch({ price: { status: 200, body: DETAIL }, news: { status: 200, body: NEWS_EMPTY } });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);
    await waitFor(() => expect(getByTestId("symbols-news-empty")).toBeInTheDocument());
  });

  it("shows the backend's actionable error message for an unknown ticker", async () => {
    nav.search = "symbol=ZZZZ";
    buildFetch({
      price: {
        status: 404,
        body: { detail: "No price data for ZZZZ. Check the symbol, e.g. AAPL, SPY." },
      },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    await waitFor(() => expect(getByTestId("symbols-error")).toBeInTheDocument());
    expect(getByTestId("symbols-error")).toHaveTextContent(/No price data for ZZZZ/);
  });

  it("exposes no buy/sell/execute button (research-only surface)", async () => {
    nav.search = "symbol=AAPL";
    buildFetch({
      price: { status: 200, body: DETAIL },
      fundamentals: { status: 200, body: FUND_US },
    });
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
    buildFetch({
      price: { status: 200, body: DETAIL },
      fundamentals: { status: 200, body: FUND_US },
    });
    const { getByTestId } = renderWithIntl(<SymbolsPage />);

    fireEvent.change(getByTestId("symbols-search-input"), { target: { value: "aapl" } });
    fireEvent.click(getByTestId("symbols-search-button"));

    await waitFor(() => expect(getByTestId("symbols-detail")).toBeInTheDocument());
    expect(nav.replace).toHaveBeenCalledWith("/symbols?symbol=AAPL");
  });
});

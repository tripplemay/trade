// @vitest-environment happy-dom
/**
 * B035 F003 — MarketContextCard renders structured market-context series
 * (label / value / date / source) and handles empty + error states. No
 * AI prose (B035 is a non-AI data-display batch).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import { MarketContextCard } from "@/components/market/MarketContextCard";

type MarketContextSeries = components["schemas"]["MarketContextSeries"];

const SERIES: MarketContextSeries[] = [
  {
    series_id: "DGS10",
    source: "fred",
    label: "10-Year Treasury Yield (%)",
    latest_value: 4.28,
    latest_date: "2026-06-03",
  },
  {
    series_id: "SPY",
    source: "alpha_vantage",
    label: "S&P 500 (SPY)",
    latest_value: 580.5,
    latest_date: "2026-06-03",
  },
  {
    series_id: "VIXCLS",
    source: "fred",
    label: "VIX — Volatility Index",
    latest_value: null,
    latest_date: null,
  },
];

function buildFetch(body: unknown, ok = true): typeof fetch {
  return vi.fn(async () =>
    ok
      ? new Response(JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      : new Response("boom", { status: 500 }),
  ) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("MarketContextCard (B035 F003)", () => {
  it("renders one cell per series with value, date, source", async () => {
    vi.stubGlobal("fetch", buildFetch({ series: SERIES }));
    const { getByTestId, getAllByTestId } = renderWithIntl(<MarketContextCard />);

    await waitFor(() => expect(getByTestId("market-context-list")).toBeInTheDocument());
    expect(getAllByTestId("market-context-series")).toHaveLength(3);

    const values = getAllByTestId("market-context-value").map((n) => n.textContent);
    expect(values).toContain("4.28");
    expect(values).toContain("580.50");
    expect(values).toContain("—"); // VIXCLS has no data → em dash

    const sources = getAllByTestId("market-context-source").map((n) => n.textContent);
    expect(sources).toContain("FRED");
    expect(sources).toContain("Alpha Vantage");
  });

  it("renders empty state when no series", async () => {
    vi.stubGlobal("fetch", buildFetch({ series: [] }));
    const { getByTestId } = renderWithIntl(<MarketContextCard />);
    await waitFor(() => expect(getByTestId("market-context-empty")).toBeInTheDocument());
  });

  it("renders error state on fetch failure", async () => {
    vi.stubGlobal("fetch", buildFetch(null, false));
    const { getByTestId } = renderWithIntl(<MarketContextCard />);
    await waitFor(() => expect(getByTestId("market-context-error")).toBeInTheDocument());
  });
});

// @vitest-environment happy-dom
/**
 * B037 F002 — the restructured three-section Home renders:
 *   ① NAV + Day P&L hero (from /api/home),
 *   ② the reused AI Advisor section (B036),
 *   ③ the reused market-context card (B035) + the sleeve breakdown.
 *
 * The page fetches /api/home; the reused sections self-fetch
 * /api/advisor + /api/market-context, so the fetch stub routes by URL.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import HomePage from "@/app/(protected)/page";
import type { components } from "@/types/api";

type HomeResponse = components["schemas"]["HomeResponse"];

const HOME_PAYLOAD: HomeResponse = {
  nav: 52500.5,
  day_pnl: { value: 320.25, pct: 0.0061 },
  sleeves: [
    { sleeve: "regime", nav_share: 0.5, day_pnl: { value: 160.0, pct: 0.006 }, positions_summary: "2 positions" },
    { sleeve: "risk_parity", nav_share: 0.5, day_pnl: { value: 160.25, pct: 0.0062 }, positions_summary: "1 position" },
    { sleeve: "satellite_us_quality", nav_share: null, day_pnl: null, positions_summary: "—" },
  ],
};

const EMPTY_PAYLOAD: HomeResponse = { nav: 0, day_pnl: null, sleeves: [] };

function routedFetch(home: HomeResponse): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/home")) {
      return new Response(JSON.stringify(home), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    // Reused advisor / market-context sections — empty payloads.
    const empty = url.includes("/api/advisor") ? { sleeves: [] } : { series: [] };
    return new Response(JSON.stringify(empty), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("HomePage (B037 F002 — three-section restructure)", () => {
  it("renders the three sections: hero, advisor, market-context + sleeves", async () => {
    vi.stubGlobal("fetch", routedFetch(HOME_PAYLOAD));
    const { getByTestId } = renderWithIntl(<HomePage />);
    expect(getByTestId("home-hero")).toBeInTheDocument();
    expect(getByTestId("home-advisor-card")).toBeInTheDocument();
    expect(getByTestId("home-market-context-card")).toBeInTheDocument();
    expect(getByTestId("home-sleeves")).toBeInTheDocument();
    await waitFor(() => {
      expect(getByTestId("home-nav")).toHaveTextContent(/\$52,500\.50/);
    });
  });

  it("colour-codes a positive Day P&L green with a + sign", async () => {
    vi.stubGlobal("fetch", routedFetch(HOME_PAYLOAD));
    const { getByTestId } = renderWithIntl(<HomePage />);
    await waitFor(() => {
      const pnl = getByTestId("home-day-pnl");
      expect(pnl).toHaveTextContent(/\+\$320\.25/);
      expect(pnl.querySelector(".text-emerald-400")).not.toBeNull();
    });
  });

  it("renders one row per sleeve with share + day P&L", async () => {
    vi.stubGlobal("fetch", routedFetch(HOME_PAYLOAD));
    const { getByTestId } = renderWithIntl(<HomePage />);
    await waitFor(() => {
      expect(getByTestId("home-sleeve-regime")).toHaveTextContent(/50\.00%/);
      expect(getByTestId("home-sleeve-satellite_us_quality")).toBeInTheDocument();
    });
  });

  it("shows the empty Day P&L state (—) when day_pnl is null", async () => {
    vi.stubGlobal("fetch", routedFetch(EMPTY_PAYLOAD));
    const { getByTestId } = renderWithIntl(<HomePage />);
    await waitFor(() => {
      expect(getByTestId("home-day-pnl")).toHaveTextContent("—");
    });
  });

  it("renders zh-CN copy for the hero NAV label", async () => {
    vi.stubGlobal("fetch", routedFetch(HOME_PAYLOAD));
    const { getByText } = renderWithIntl(<HomePage />, { locale: "zh-CN" });
    expect(getByText("净资产")).toBeInTheDocument();
  });

  it("surfaces a fetch failure in the state line without crashing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 500 })) as unknown as typeof fetch,
    );
    const { getByTestId } = renderWithIntl(<HomePage />);
    await waitFor(() => {
      expect(getByTestId("home-state")).toHaveTextContent(/unreachable/);
    });
    expect(getByTestId("home-nav")).toHaveTextContent("—");
  });
});

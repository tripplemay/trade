// @vitest-environment happy-dom
/**
 * B023 F005 — Journal history page: renders 12-month seeded list +
 * slippage analytics summary + window switch + outlier badges.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

vi.mock("ag-grid-react", () => ({
  AgGridReact: ({ rowData }: { rowData?: unknown[] }) => (
    <div data-testid="ag-grid-mock">rows={rowData?.length ?? 0}</div>
  ),
}));
vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: vi.fn() },
  themeQuartz: { withPart: () => ({}) },
  colorSchemeDark: {},
}));
vi.mock("echarts-for-react", () => ({ default: () => null }));

import JournalHistoryPage from "@/app/(protected)/execution/journal-history/page";

type JournalHistoryResponse = components["schemas"]["JournalHistoryResponse"];
type SlippageAnalyticsResponse = components["schemas"]["SlippageAnalyticsResponse"];

function makeItem(
  index: number,
  status: "executed" | "voided" | "generated" = "executed",
): JournalHistoryResponse["items"][0] {
  return {
    ticket_id: `tkt-${index.toString().padStart(2, "0")}`,
    ticket_date: `2026-${(index + 1).toString().padStart(2, "0")}-01`,
    status,
    snapshot_id: "snap-x",
    markdown_path: "docs/runs/.../order-ticket-x.md",
    created_at: "2026-05-19T10:00:00",
    executed_at: status === "executed" ? "2026-05-19T17:00:00" : null,
    fill_count: 3 + index,
    avg_bps: status === "executed" ? 10 + index : null,
    total_dollar: status === "executed" ? -5.5 + index : 0,
  };
}

const HISTORY: JournalHistoryResponse = {
  since: null,
  items: Array.from({ length: 12 }, (_, i) => makeItem(11 - i)),
};

const ANALYTICS_3M: SlippageAnalyticsResponse = {
  window: "3m",
  rolling_avg_bps: 15.0,
  outliers: [{ ticket_id: "tkt-99", ticket_date: "2026-04-15", avg_bps: 100.5 }],
  trend: [
    { month: "2026-03", avg_bps: 12.0, fill_count: 5 },
    { month: "2026-04", avg_bps: 14.0, fill_count: 6 },
    { month: "2026-05", avg_bps: 18.0, fill_count: 8 },
  ],
};

const ANALYTICS_1Y: SlippageAnalyticsResponse = {
  window: "1y",
  rolling_avg_bps: 9.0,
  outliers: [],
  trend: [],
};

interface MockState {
  history: JournalHistoryResponse;
  analytics: SlippageAnalyticsResponse;
  analytics1y: SlippageAnalyticsResponse;
}

function buildFetch(state: MockState): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? input.toString());
    // B057 F005 — the journal endpoint now carries a ?strategy_id= query (the
    // analytics matchers below already use startsWith, so they are unaffected).
    if ((url.split("?")[0] ?? url) === "/api/execution/journal-history") {
      return new Response(JSON.stringify(state.history), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.startsWith("/api/execution/slippage-analytics?window=1y")) {
      return new Response(JSON.stringify(state.analytics1y), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.startsWith("/api/execution/slippage-analytics")) {
      return new Response(JSON.stringify(state.analytics), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not-found", { status: 404 });
  }) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("JournalHistoryPage (B023 F005)", () => {
  it("renders 12 seeded tickets + state line + summary cards", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({ history: HISTORY, analytics: ANALYTICS_3M, analytics1y: ANALYTICS_1Y }),
    );
    const { getByTestId } = renderWithIntl(<JournalHistoryPage />);
    await waitFor(() => {
      expect(getByTestId("journal-history-state")).toHaveTextContent("12 ticket(s) on file");
    });
    expect(getByTestId("ag-grid-mock")).toHaveTextContent("rows=12");
    expect(getByTestId("journal-card-count")).toHaveTextContent("12");
    // Outlier surfaces.
    expect(getByTestId("journal-outlier-tkt-99")).toBeInTheDocument();
  });

  it("renders empty-state when no tickets are seeded", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        history: { since: null, items: [] },
        analytics: { window: "3m", rolling_avg_bps: null, outliers: [], trend: [] },
        analytics1y: ANALYTICS_1Y,
      }),
    );
    const { getByTestId } = renderWithIntl(<JournalHistoryPage />);
    await waitFor(() => {
      expect(getByTestId("journal-history-empty")).toBeInTheDocument();
      expect(getByTestId("journal-trend-empty")).toBeInTheDocument();
    });
  });

  it("window switch re-fetches the analytics endpoint", async () => {
    const fetchMock = buildFetch({
      history: HISTORY,
      analytics: ANALYTICS_3M,
      analytics1y: ANALYTICS_1Y,
    });
    vi.stubGlobal("fetch", fetchMock);
    const { getByTestId } = renderWithIntl(<JournalHistoryPage />);
    await waitFor(() => {
      expect(getByTestId("journal-history-state")).toHaveTextContent("12 ticket(s) on file");
    });
    fireEvent.change(getByTestId("journal-window-select"), { target: { value: "1y" } });
    await waitFor(() => {
      const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
      const urls = calls.map(([arg]) =>
        typeof arg === "string" ? arg : (arg as Request | URL).toString(),
      );
      expect(urls.some((u) => u.includes("window=1y"))).toBe(true);
    });
  });

  it("uses same-origin /api path (no 127.0.0.1)", async () => {
    const fetchMock = buildFetch({
      history: HISTORY,
      analytics: ANALYTICS_3M,
      analytics1y: ANALYTICS_1Y,
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithIntl(<JournalHistoryPage />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    for (const [arg] of calls) {
      const url = typeof arg === "string" ? arg : (arg as Request | URL).toString();
      expect(url).not.toMatch(/127\.0\.0\.1/);
      expect(url.startsWith("/api/")).toBe(true);
    }
  });
});

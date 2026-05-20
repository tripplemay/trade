// @vitest-environment happy-dom
/**
 * B023 F002 — Position diff page renders the diff table + handles
 * empty + unmatched-target states. AG Grid + chart wrappers are mocked
 * at module scope so we focus on page-level wiring (state ↔ fetch ↔
 * derived counts).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

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

import PositionDiffPage from "@/app/(protected)/execution/position-diff/page";

type PositionDiffResponse = components["schemas"]["PositionDiffResponse"];

const SEEDED: PositionDiffResponse = {
  as_of_date: "2026-05-18",
  total_equity: 55_000,
  current: {
    id: "snap-test-1",
    snapshot_at: "2026-05-18T10:00:00",
    cash: 50_000,
    base_currency: "USD",
    positions: [{ symbol: "B013", shares: 10, avg_cost: 500 }],
    source: "bootstrap",
  },
  target: [
    { symbol: "B013", shares: 27.5, avg_cost: 500 },
    { symbol: "B014", shares: 0, avg_cost: 0 },
  ],
  diff: [
    {
      symbol: "B013",
      current_shares: 10,
      target_shares: 27.5,
      delta_shares: 17.5,
      current_weight: 0.0909,
      target_weight: 0.25,
      delta_weight: 0.1591,
      delta_dollar: 8750,
      reference_price: 500,
      reason: "Sleeve regime → target weight",
    },
    {
      symbol: "B014",
      current_shares: 0,
      target_shares: 0,
      delta_shares: 0,
      current_weight: 0,
      target_weight: 0.25,
      delta_weight: 0.25,
      delta_dollar: 0,
      reference_price: null,
      reason: "Sleeve regime → target weight",
    },
  ],
  unmatched: [
    {
      symbol: "B014",
      current_shares: 0,
      target_shares: 0,
      delta_shares: 0,
      current_weight: 0,
      target_weight: 0.25,
      delta_weight: 0.25,
      delta_dollar: 0,
      reference_price: null,
      reason: "Sleeve regime → target weight",
    },
  ],
};

const EMPTY: PositionDiffResponse = {
  as_of_date: "2026-05-18",
  total_equity: 0,
  current: null,
  target: [],
  diff: [],
  unmatched: [],
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

describe("PositionDiffPage (B023 F002)", () => {
  it("renders the diff table + state line + unmatched warning when seeded", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/execution/position-diff": SEEDED }));
    const { getByTestId } = renderWithIntl(<PositionDiffPage />);
    await waitFor(() => {
      expect(getByTestId("position-diff-state")).toHaveTextContent(/as of 2026-05-18/);
    });
    expect(getByTestId("ag-grid-mock")).toHaveTextContent(/rows=2/);
    expect(getByTestId("position-diff-unmatched-B014")).toBeInTheDocument();
  });

  it("renders empty-state when no snapshot is on file", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/execution/position-diff": EMPTY }));
    const { getByTestId } = renderWithIntl(<PositionDiffPage />);
    await waitFor(() => {
      expect(getByTestId("position-diff-empty")).toBeInTheDocument();
    });
    expect(getByTestId("position-diff-unmatched-empty")).toBeInTheDocument();
  });

  it("uses same-origin /api path (no 127.0.0.1, no absolute URL)", async () => {
    const fetchMock = buildFetch({ "/api/execution/position-diff": SEEDED });
    vi.stubGlobal("fetch", fetchMock);
    renderWithIntl(<PositionDiffPage />);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const calls = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    for (const [arg] of calls) {
      const url = typeof arg === "string" ? arg : (arg as Request | URL).toString();
      expect(url).not.toMatch(/127\.0\.0\.1/);
      expect(url.startsWith("/api/")).toBe(true);
    }
  });
});

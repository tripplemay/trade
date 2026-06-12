// @vitest-environment happy-dom
/**
 * B022 F010 — Recommendations page renders disclaimer + gate panel +
 * wash-sale flags + positions table; export button POSTs and surfaces
 * the written-path message.
 *
 * AG Grid + chart wrappers mocked at module scope; we focus on the
 * page-level wiring (state ↔ fetch ↔ exported file path).
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

import RecommendationsPage from "@/app/(protected)/recommendations/page";

const RECS: components["schemas"]["RecommendationsResponse"] = {
  as_of_date: "2026-05-17",
  target_positions: [
    {
      symbol: "B013",
      target_weight: 0.25,
      current_weight: 0,
      diff: 0.25,
      rationale: "Sleeve regime",
      has_mark: true,
    },
    {
      symbol: "B016",
      target_weight: 0.25,
      current_weight: 0,
      diff: 0.25,
      rationale: "Sleeve risk_parity",
      has_mark: true,
    },
  ],
  gate_checks: [
    { name: "kill_switch", status: "pass", detail: "DD 0.00 ≤ 0.20" },
    { name: "min_equity", status: "pass", detail: "Equity 50000" },
  ],
  wash_sale_flags: [],
  account_present: true,
};

const EXPORT: components["schemas"]["ExportTicketResponse"] = {
  path: "docs/runs/2026-05-17/order-ticket-2026-05-17.md",
  disclaimer: "research-only; this is a manual review checklist, not a trading instruction",
};

function buildFetch(map: Record<string, unknown>): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? input.toString());
    // B057 F005 — match on the path, ignoring the ?strategy_id= query the mode
    // selector adds (the page now passes the selected strategy mode through).
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

describe("RecommendationsPage (B022 F010)", () => {
  it("renders disclaimer + state line + gate checks + simplified position cards (default)", async () => {
    vi.stubGlobal("fetch", buildFetch({ "/api/recommendations/current": RECS }));
    const { getByTestId } = renderWithIntl(<RecommendationsPage />);
    expect(getByTestId("recommendations-disclaimer-card")).toBeInTheDocument();
    await waitFor(() => {
      expect(getByTestId("recommendations-state")).toHaveTextContent(/account present/);
      expect(getByTestId("gate-kill_switch")).toHaveTextContent(/pass/i);
    });
    expect(getByTestId("recommendations-wash-empty")).toBeInTheDocument();
    // B041: target positions now default to the simplified card view.
    await waitFor(() => {
      expect(getByTestId("position-cards")).toBeInTheDocument();
      expect(getByTestId("position-card-B013")).toBeInTheDocument();
      expect(getByTestId("position-card-B016")).toBeInTheDocument();
    });
  });

  it("exposes both view toggles with the simplified card view as default (B041)", async () => {
    // The actual radix Tabs switch interaction is covered by the Playwright
    // e2e (real Chromium); radix tab activation is unreliable to drive in
    // happy-dom without user-event. Here we pin the structure + default.
    vi.stubGlobal("fetch", buildFetch({ "/api/recommendations/current": RECS }));
    const { getByTestId, queryByTestId } = renderWithIntl(<RecommendationsPage />);
    await waitFor(() => expect(getByTestId("position-cards")).toBeInTheDocument());
    expect(getByTestId("view-toggle-simple")).toBeInTheDocument();
    expect(getByTestId("view-toggle-professional")).toBeInTheDocument();
    // Default = simplified cards; the professional AG Grid table is not mounted.
    expect(queryByTestId("ag-grid-mock")).toBeNull();
  });

  it("renders empty-state when account_present is false", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/recommendations/current": {
          ...RECS,
          account_present: false,
          target_positions: [],
        },
      }),
    );
    const { getByTestId } = renderWithIntl(<RecommendationsPage />);
    await waitFor(() => {
      expect(getByTestId("recommendations-empty")).toBeInTheDocument();
    });
  });

  it("export button POSTs and surfaces the written path", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/recommendations/current": RECS,
        "/api/recommendations/export-ticket": EXPORT,
      }),
    );
    const { getByTestId } = renderWithIntl(<RecommendationsPage />);
    await waitFor(() => {
      expect(getByTestId("recommendations-export")).not.toBeDisabled();
    });
    fireEvent.click(getByTestId("recommendations-export"));
    await waitFor(() => {
      expect(getByTestId("recommendations-export-result")).toHaveTextContent(
        "docs/runs/2026-05-17/order-ticket-2026-05-17.md",
      );
    });
  });

  // B058 F005 — manual "refresh target" button (enqueue → poll → done / error).
  it("refresh-target button enqueues + polls to done and surfaces the result", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/recommendations/current": RECS,
        "/api/strategy-modes/master_portfolio/refresh-target": {
          job_id: "trf-1",
          strategy_id: "master_portfolio",
          status: "queued",
        },
        "/api/strategy-modes/refresh-target/trf-1": {
          job_id: "trf-1",
          strategy_id: "master_portfolio",
          status: "done",
          as_of_date: "2026-06-12",
          saved_count: 6,
          data_source: "real",
          error: null,
          error_kind: null,
        },
      }),
    );
    const { getByTestId } = renderWithIntl(<RecommendationsPage />);
    await waitFor(() => expect(getByTestId("recommendations-refresh-target")).not.toBeDisabled());
    fireEvent.click(getByTestId("recommendations-refresh-target"));
    await waitFor(() => {
      expect(getByTestId("recommendations-refresh-result")).toHaveTextContent(/2026-06-12/);
    });
  });

  it("refresh-target error surfaces the bilingual error_kind message", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/recommendations/current": RECS,
        "/api/strategy-modes/master_portfolio/refresh-target": {
          job_id: "trf-2",
          strategy_id: "master_portfolio",
          status: "queued",
        },
        "/api/strategy-modes/refresh-target/trf-2": {
          job_id: "trf-2",
          strategy_id: "master_portfolio",
          status: "error",
          error: "no rows",
          error_kind: "empty_target",
        },
      }),
    );
    const { getByTestId } = renderWithIntl(<RecommendationsPage />);
    await waitFor(() => expect(getByTestId("recommendations-refresh-target")).not.toBeDisabled());
    fireEvent.click(getByTestId("recommendations-refresh-target"));
    await waitFor(() => {
      expect(getByTestId("recommendations-refresh-error")).toBeInTheDocument();
    });
  });

  it("refresh-target data_not_covered error shows the actionable refresh-data message", async () => {
    vi.stubGlobal(
      "fetch",
      buildFetch({
        "/api/recommendations/current": RECS,
        "/api/strategy-modes/master_portfolio/refresh-target": {
          job_id: "trf-3",
          strategy_id: "master_portfolio",
          status: "queued",
        },
        "/api/strategy-modes/refresh-target/trf-3": {
          job_id: "trf-3",
          strategy_id: "master_portfolio",
          status: "error",
          error: "regime price coverage incomplete — missing ['DBC']",
          error_kind: "data_not_covered",
        },
      }),
    );
    const { getByTestId } = renderWithIntl(<RecommendationsPage />);
    await waitFor(() => expect(getByTestId("recommendations-refresh-target")).not.toBeDisabled());
    fireEvent.click(getByTestId("recommendations-refresh-target"));
    await waitFor(() => {
      // Actionable guidance, not a vague "producer error".
      expect(getByTestId("recommendations-refresh-error")).toHaveTextContent(
        /data-refresh|does not cover/i,
      );
    });
  });
});

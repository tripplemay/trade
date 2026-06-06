// @vitest-environment happy-dom
/**
 * B022 F009 — Reports list + detail page wiring.
 *
 * Mocks fetch + AG Grid + Radix Select; the markdown renderer is
 * exercised with its actual react-markdown + remark-gfm pipeline so
 * the table-row counting and cross-link rewrite paths get coverage.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

const paramsRef: { value: { slug?: string; path?: string[] } } = { value: {} };
vi.mock("next/navigation", () => ({
  useParams: () => paramsRef.value,
  useSearchParams: () => new URLSearchParams(),
}));

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

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const LIST_PAYLOAD: components["schemas"]["ReportListResponse"] = {
  reports: [
    {
      slug: "B019-retune-signoff",
      title: "B019 retune signoff",
      date: "2026-05-15",
      batch: "B019",
      kind: "signoff",
      path: "docs/test-reports/B019-retune-signoff-2026-05-15.md",
    },
  ],
};

const HEAVY_MD = `# Sweep matrix

| window | nav | dd | turnover | sharpe |
|---|---:|---:|---:|---:|
${Array.from({ length: 12 }, (_, i) => `| w${i} | ${100 + i} | -0.0${i} | 1.${i} | ${i / 10} |`).join("\n")}
`;

const DETAIL_PAYLOAD: components["schemas"]["ReportDetail"] = {
  slug: "B019-retune-signoff",
  title: "B019 retune signoff",
  date: "2026-05-15",
  batch: "B019",
  kind: "signoff",
  body_markdown: HEAVY_MD,
  tables: [],
  cross_links: ["docs/specs/B015-regime-adaptive-activation-policy-spec.md"],
};

const DETAIL_WITH_METRICS: components["schemas"]["ReportDetail"] = {
  ...DETAIL_PAYLOAD,
  metrics: {
    sharpe: 2.42,
    sortino: null,
    calmar: 4.46,
    cagr: 0.025,
    max_drawdown: -0.0056,
    volatility: 0.0103,
    turnover: 1.09,
  },
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  paramsRef.value = {};
});

describe("ReportsPage (list)", () => {
  it("renders summaries with deep-link", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(LIST_PAYLOAD)) as unknown as typeof fetch,
    );
    const { default: ReportsPage } = await import("@/app/(protected)/reports/page");
    const { getByTestId } = renderWithIntl(<ReportsPage />);
    await waitFor(() => {
      const link = getByTestId("report-link-B019-retune-signoff");
      expect(link).toHaveAttribute("href", "/reports/B019-retune-signoff");
    });
  });
});

describe("ReportDetailPage (heavy-table swap-in)", () => {
  // react-markdown + remark-gfm + the table parser are noticeably slower
  // than the chart-mock specs; bump the per-test timeout above the 5s
  // vitest default so the run survives load on a cold CI runner.
  it("fetches the detail and renders AG Grid for the ≥10-row table", async () => {
    paramsRef.value = { slug: "B019-retune-signoff" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(DETAIL_PAYLOAD)) as unknown as typeof fetch,
    );
    const { default: ReportDetailPage } = await import("@/app/(protected)/reports/[slug]/page");
    const { getByTestId } = renderWithIntl(<ReportDetailPage />);
    await waitFor(() => {
      expect(getByTestId("report-detail-state")).toHaveTextContent(/B019.*signoff.*2026-05-15/);
    });
    // The 12-row markdown table should swap into AG Grid (12 ≥ 10).
    await waitFor(() => {
      expect(getByTestId("markdown-heavy-table")).toBeInTheDocument();
      expect(getByTestId("ag-grid-mock")).toHaveTextContent(/rows=12/);
    });
    // Cross-links Card renders with the spec path.
    expect(getByTestId("report-detail-cross-links")).toHaveTextContent(
      "docs/specs/B015-regime-adaptive-activation-policy-spec.md",
    );
  }, 25_000);
});

describe("ReportDetailPage (B040 metrics card)", () => {
  it("renders the big-number metrics card above the markdown when metrics present", async () => {
    paramsRef.value = { slug: "B019-retune-signoff" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(DETAIL_WITH_METRICS)) as unknown as typeof fetch,
    );
    const { default: ReportDetailPage } = await import("@/app/(protected)/reports/[slug]/page");
    const { getByTestId } = renderWithIntl(<ReportDetailPage />);
    await waitFor(() => expect(getByTestId("report-metrics")).toBeInTheDocument());
    expect(getByTestId("metric-value-sharpe")).toHaveTextContent("2.42");
    expect(getByTestId("metric-value-cagr")).toHaveTextContent("2.50%");
    // body_markdown integrity: the markdown table still renders below,
    // unchanged by the metrics card (the card is an independent section).
    await waitFor(() => expect(getByTestId("ag-grid-mock")).toHaveTextContent(/rows=12/));
  }, 25_000);

  it("renders markdown only (no metrics card) when metrics is null — graceful", async () => {
    paramsRef.value = { slug: "B019-retune-signoff" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(DETAIL_PAYLOAD)) as unknown as typeof fetch,
    );
    const { default: ReportDetailPage } = await import("@/app/(protected)/reports/[slug]/page");
    const { getByTestId, queryByTestId } = renderWithIntl(<ReportDetailPage />);
    await waitFor(() => expect(getByTestId("report-detail-state")).toHaveTextContent(/B019/));
    expect(queryByTestId("report-metrics")).toBeNull();
    await waitFor(() => expect(getByTestId("ag-grid-mock")).toBeInTheDocument());
  }, 25_000);
});

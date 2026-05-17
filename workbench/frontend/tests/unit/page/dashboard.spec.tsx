// @vitest-environment happy-dom
/**
 * B022 F006 Vitest mock — Home (Dashboard) page renders the 4 cards,
 * the recent-reports list, the action-items list, and the corresponding
 * empty states when arrays are empty.
 *
 * The page fetches /api/dashboard via the global fetch; we stub fetch
 * before render so the useEffect resolves with the mocked payload and
 * the cards transition out of "—" placeholders.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import HomePage from "@/app/(protected)/page";
import type { components } from "@/types/api";

type DashboardResponse = components["schemas"]["DashboardResponse"];

function jsonResponse(payload: DashboardResponse): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const FULL_PAYLOAD: DashboardResponse = {
  nav: 52500.5,
  master_drawdown: -0.062,
  kill_switch_threshold: 0.2,
  days_to_next_rebalance: 14,
  last_rebalance: { date: "2026-05-01", fill_count: 4, slippage_bps: 3.2 },
  recent_reports: [
    {
      id: "B019-retune-signoff",
      title: "B019 retune signoff",
      date: "2026-05-15",
      status: "signoff",
      path: "docs/test-reports/B019-retune-signoff.md",
    },
  ],
  action_items: [
    { id: "kill-switch-warn", severity: "warning", message: "Drawdown 12% — halve sleeve" },
  ],
};

const EMPTY_PAYLOAD: DashboardResponse = {
  nav: 0,
  master_drawdown: 0,
  kill_switch_threshold: 0.2,
  days_to_next_rebalance: 0,
  last_rebalance: null,
  recent_reports: [],
  action_items: [],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("HomePage (B022 F006)", () => {
  it("renders the 4 dashboard cards immediately (skeleton-then-value)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(FULL_PAYLOAD)) as unknown as typeof fetch);
    const { getByTestId } = render(<HomePage />);
    // Cards render synchronously with placeholder "—" values.
    for (const id of [
      "dashboard-card-nav",
      "dashboard-card-drawdown",
      "dashboard-card-killswitch",
      "dashboard-card-rebalance",
    ]) {
      expect(getByTestId(id)).toBeInTheDocument();
    }
    // After the fetch resolves the NAV card shows the formatted value.
    await waitFor(() => {
      expect(getByTestId("dashboard-card-nav")).toHaveTextContent(/\$52,500\.50/);
    });
  });

  it("renders the recent reports list with Link → /reports/{slug}", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(FULL_PAYLOAD)) as unknown as typeof fetch);
    const { getByTestId } = render(<HomePage />);
    await waitFor(() => {
      const link = getByTestId("recent-report-B019-retune-signoff");
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", "/reports/B019-retune-signoff");
    });
  });

  it("renders the empty-state copy when arrays are empty", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(EMPTY_PAYLOAD)) as unknown as typeof fetch);
    const { getByTestId } = render(<HomePage />);
    await waitFor(() => {
      expect(getByTestId("recent-reports-empty")).toBeInTheDocument();
      expect(getByTestId("action-items-empty")).toBeInTheDocument();
    });
  });

  it("surfaces a fetch failure in the state line without crashing the cards", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 500 })) as unknown as typeof fetch,
    );
    const { getByTestId } = render(<HomePage />);
    await waitFor(() => {
      expect(getByTestId("dashboard-state")).toHaveTextContent(/unreachable/);
    });
    // Cards still render their skeletons.
    expect(getByTestId("dashboard-card-nav")).toHaveTextContent("—");
  });
});

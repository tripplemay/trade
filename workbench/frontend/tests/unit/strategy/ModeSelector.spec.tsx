// @vitest-environment happy-dom
/**
 * B057 F005 — the strategy-mode selector renders one pill per platform mode
 * (from /api/strategy-modes), marks research-state modes "研究态" + shows the
 * "前向验证中" notice, and switching the mode updates the shared selection.
 * With ≤1 mode (Master-only) it renders nothing — the existing single-account
 * experience is byte-identical.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, waitFor } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import { ModeSelector } from "@/components/strategy/ModeSelector";
import { StrategyModeProvider, useStrategyMode } from "@/lib/strategy-mode";

const MASTER = {
  id: "master",
  strategy_id: "master_portfolio",
  display_name: "旗舰组合",
  funding_state: "live",
  is_research_state: false,
  cadence: "quarterly",
  description: "旗舰",
};
const REGIME = {
  id: "regime",
  strategy_id: "regime_adaptive",
  display_name: "智能择时组合",
  funding_state: "research",
  is_research_state: true,
  cadence: "monthly",
  description: "研究态",
};

function mockModes(modes: unknown[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ modes }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch,
  );
}

/** A probe that exposes the current selection for assertions. */
function SelectionProbe() {
  const { strategyId } = useStrategyMode();
  return <span data-testid="selected">{strategyId}</span>;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  try {
    window.localStorage.clear();
  } catch {
    /* ignore */
  }
});

describe("ModeSelector (B057 F005)", () => {
  it("renders a pill per mode and marks the research mode + notice", async () => {
    mockModes([MASTER, REGIME]);
    const { getByText, getByTestId } = renderWithIntl(
      <StrategyModeProvider>
        <ModeSelector />
      </StrategyModeProvider>,
    );
    await waitFor(() => {
      expect(getByTestId("mode-selector")).toBeInTheDocument();
    });
    // Mode display names come from the API (always the canonical Chinese name);
    // the badge label comes from i18n (the test bundle renders the en locale).
    expect(getByText("旗舰组合")).toBeInTheDocument();
    expect(getByText("智能择时组合")).toBeInTheDocument();
    // Research badge present (regime), and the default (Master) is funded so the
    // forward-validation notice is NOT shown for the default selection.
    expect(getByText("Research")).toBeInTheDocument();
  });

  it("switching to the research mode updates the selection + shows the notice", async () => {
    mockModes([MASTER, REGIME]);
    const { getByText, getByTestId, queryByTestId } = renderWithIntl(
      <StrategyModeProvider>
        <ModeSelector />
        <SelectionProbe />
      </StrategyModeProvider>,
    );
    await waitFor(() => expect(getByTestId("mode-selector")).toBeInTheDocument());
    // Default selection is Master; no research notice yet.
    expect(getByTestId("selected")).toHaveTextContent("master_portfolio");
    expect(queryByTestId("mode-research-notice")).toBeNull();

    fireEvent.click(getByText("智能择时组合"));
    await waitFor(() => {
      expect(getByTestId("selected")).toHaveTextContent("regime_adaptive");
      expect(getByTestId("mode-research-notice")).toBeInTheDocument();
    });
  });

  it("renders nothing when only the flagship mode exists (Master-only parity)", async () => {
    mockModes([MASTER]);
    const { queryByTestId } = renderWithIntl(
      <StrategyModeProvider>
        <ModeSelector />
      </StrategyModeProvider>,
    );
    // Give the fetch a tick; the selector stays hidden (≤1 mode).
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(queryByTestId("mode-selector")).toBeNull();
  });
});

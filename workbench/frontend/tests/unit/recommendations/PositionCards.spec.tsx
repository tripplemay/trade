// @vitest-environment happy-dom
/**
 * B041 F001 — PositionCards renders the simplified target-positions cards:
 * symbol + target/current/delta big numbers, colour-coded delta, rationale
 * text, and no execution affordance.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import type { components } from "@/types/api";

import { PositionCards } from "@/components/recommendations/PositionCards";

type TargetPosition = components["schemas"]["TargetPosition"];

const POSITIONS: TargetPosition[] = [
  {
    symbol: "AAPL",
    target_weight: 0.25,
    current_weight: 0.1,
    diff: 0.15, // buy → green
    rationale: "Equal-weight placeholder allocation.",
    has_mark: true,
  },
  {
    symbol: "MSFT",
    target_weight: 0.1,
    current_weight: 0.3,
    diff: -0.2, // trim → red
    rationale: null,
    has_mark: true,
  },
];

afterEach(cleanup);

describe("PositionCards (B041 F001)", () => {
  it("renders one card per position with target/current/delta big numbers", () => {
    const { getByTestId } = renderWithIntl(<PositionCards positions={POSITIONS} />);
    expect(getByTestId("position-card-AAPL")).toBeInTheDocument();
    expect(getByTestId("position-card-MSFT")).toBeInTheDocument();
    expect(getByTestId("position-card-AAPL")).toHaveTextContent("25.00%"); // target
    expect(getByTestId("position-card-AAPL")).toHaveTextContent("10.00%"); // current
    expect(getByTestId("position-delta-AAPL")).toHaveTextContent("+15.00%");
    expect(getByTestId("position-delta-MSFT")).toHaveTextContent("-20.00%");
  });

  it("colour-codes the delta (buy green, trim red)", () => {
    const { getByTestId } = renderWithIntl(<PositionCards positions={POSITIONS} />);
    expect(getByTestId("position-delta-AAPL").className).toContain("emerald");
    expect(getByTestId("position-delta-MSFT").className).toContain("red");
  });

  it("surfaces the rationale text when present, omits it when null", () => {
    const { getByTestId, getAllByTestId } = renderWithIntl(<PositionCards positions={POSITIONS} />);
    expect(getByTestId("position-card-AAPL")).toHaveTextContent("Equal-weight placeholder");
    // Only AAPL has a rationale → exactly one rationale node.
    expect(getAllByTestId("position-rationale")).toHaveLength(1);
  });

  it("has no execution / order button (research-only; rebalance via export-to-ticket)", () => {
    const { container } = renderWithIntl(<PositionCards positions={POSITIONS} />);
    expect(container.querySelector("button")).toBeNull();
  });

  it("renders an empty state when there are no positions", () => {
    const { getByTestId } = renderWithIntl(<PositionCards positions={[]} />);
    expect(getByTestId("position-cards-empty")).toBeInTheDocument();
  });

  it("shows a 'held, no price' label instead of 0% when has_mark is false (B053 F003)", () => {
    const unpriced: TargetPosition[] = [
      {
        symbol: "SGOV",
        target_weight: 0.6,
        current_weight: 0, // unpriced holding reads 0 — must NOT show as a real 0%
        diff: 0.6,
        rationale: null,
        has_mark: false,
      },
    ];
    const en = renderWithIntl(<PositionCards positions={unpriced} />, { locale: "en" });
    expect(en.getByTestId("position-current-SGOV")).toHaveTextContent("Held");
    expect(en.getByTestId("position-current-SGOV")).not.toHaveTextContent("0.00%");
    cleanup();
    const zh = renderWithIntl(<PositionCards positions={unpriced} />, { locale: "zh-CN" });
    expect(zh.getByTestId("position-current-SGOV")).toHaveTextContent("持有");
  });

  it("renders bilingual field labels (en + zh-CN)", () => {
    const en = renderWithIntl(<PositionCards positions={POSITIONS} />, { locale: "en" });
    expect(en.getAllByTestId("position-label-target")[0]).toHaveTextContent("Target");
    cleanup();
    const zh = renderWithIntl(<PositionCards positions={POSITIONS} />, { locale: "zh-CN" });
    expect(zh.getAllByTestId("position-label-target")[0]).toHaveTextContent("目标");
  });
});

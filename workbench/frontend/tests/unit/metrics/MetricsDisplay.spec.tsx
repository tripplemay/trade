// @vitest-environment happy-dom
/**
 * B040 F002 — MetricsDisplay renders English term labels, colour-coded
 * formatted values, and carries no execution affordance.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";

import { renderWithIntl } from "../../test-utils/intl";

import { MetricsDisplay, type MetricStat } from "@/components/metrics/MetricsDisplay";

const STATS: MetricStat[] = [
  { key: "cagr", value: 0.1966, format: "percent" },
  { key: "sharpe", value: 2.5, format: "ratio" },
  { key: "sortino", value: null, format: "ratio" },
  { key: "calmar", value: 4.46, format: "ratio" },
  { key: "maxDrawdown", value: -0.25, format: "percent" },
  { key: "turnover", value: 1.09, format: "ratio" },
];

afterEach(cleanup);

describe("MetricsDisplay (B040 F002)", () => {
  it("renders Chinese term labels + formatted values (null → em dash)", () => {
    const { getByTestId } = renderWithIntl(<MetricsDisplay stats={STATS} />);
    // B054 fix-round 1 — metric labels are now Simplified Chinese.
    expect(getByTestId("metric-sharpe")).toHaveTextContent("夏普比率");
    expect(getByTestId("metric-value-sharpe")).toHaveTextContent("2.50");
    expect(getByTestId("metric-value-cagr")).toHaveTextContent("19.66%");
    expect(getByTestId("metric-value-maxDrawdown")).toHaveTextContent("-25.00%");
    expect(getByTestId("metric-value-sortino")).toHaveTextContent("—");
  });

  it("colour-codes values (sharpe ≥1 emerald, mdd < -0.2 red, turnover neutral)", () => {
    const { getByTestId } = renderWithIntl(<MetricsDisplay stats={STATS} />);
    expect(getByTestId("metric-value-sharpe").className).toContain("emerald");
    expect(getByTestId("metric-value-maxDrawdown").className).toContain("red");
    expect(getByTestId("metric-value-turnover").className).toContain("text-foreground");
  });

  it("has no execution / order button (research-only display)", () => {
    const { container } = renderWithIntl(<MetricsDisplay stats={STATS} />);
    expect(container.querySelector("button")).toBeNull();
  });
});

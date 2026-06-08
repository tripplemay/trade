/**
 * B040 F002 — colorForMetric threshold boundaries (spec §4.2).
 */
import { describe, expect, it } from "vitest";

import {
  colorForDelta,
  colorForDrawdown,
  colorForMetric,
  colorForRiskState,
  METRIC_COLOR,
  RISK_STATE_STYLES,
} from "@/lib/metric-color";

describe("colorForMetric", () => {
  it("ratio metrics (sharpe/sortino/calmar): >=1 positive, 0–1 warning, <0 negative", () => {
    for (const key of ["sharpe", "sortino", "calmar"] as const) {
      expect(colorForMetric(key, 2.5)).toBe(METRIC_COLOR.positive);
      expect(colorForMetric(key, 1)).toBe(METRIC_COLOR.positive);
      expect(colorForMetric(key, 0.5)).toBe(METRIC_COLOR.warning);
      expect(colorForMetric(key, 0)).toBe(METRIC_COLOR.warning);
      expect(colorForMetric(key, -1)).toBe(METRIC_COLOR.negative);
    }
  });

  it("cagr: >0 positive, <0 negative, 0 neutral", () => {
    expect(colorForMetric("cagr", 0.2)).toBe(METRIC_COLOR.positive);
    expect(colorForMetric("cagr", -0.1)).toBe(METRIC_COLOR.negative);
    expect(colorForMetric("cagr", 0)).toBe(METRIC_COLOR.neutral);
  });

  it("maxDrawdown: three tiers (>-0.05 / -0.2..-0.05 / <-0.2)", () => {
    expect(colorForMetric("maxDrawdown", -0.03)).toBe(METRIC_COLOR.positive);
    expect(colorForMetric("maxDrawdown", -0.05)).toBe(METRIC_COLOR.warning);
    expect(colorForMetric("maxDrawdown", -0.15)).toBe(METRIC_COLOR.warning);
    expect(colorForMetric("maxDrawdown", -0.2)).toBe(METRIC_COLOR.warning);
    expect(colorForMetric("maxDrawdown", -0.25)).toBe(METRIC_COLOR.negative);
  });

  it("volatility / turnover are neutral (no colour judgement)", () => {
    expect(colorForMetric("volatility", 0.3)).toBe(METRIC_COLOR.neutral);
    expect(colorForMetric("turnover", 5)).toBe(METRIC_COLOR.neutral);
  });

  it("null / undefined / NaN → neutral (empty cell)", () => {
    expect(colorForMetric("sharpe", null)).toBe(METRIC_COLOR.neutral);
    expect(colorForMetric("sharpe", undefined)).toBe(METRIC_COLOR.neutral);
    expect(colorForMetric("sharpe", Number.NaN)).toBe(METRIC_COLOR.neutral);
  });
});

describe("colorForDelta (B041 rebalance direction)", () => {
  it("positive buy → green, negative trim → red, flat → neutral", () => {
    expect(colorForDelta(0.15)).toBe(METRIC_COLOR.positive);
    expect(colorForDelta(-0.2)).toBe(METRIC_COLOR.negative);
    expect(colorForDelta(0)).toBe(METRIC_COLOR.neutral);
  });

  it("null / undefined / NaN → neutral", () => {
    expect(colorForDelta(null)).toBe(METRIC_COLOR.neutral);
    expect(colorForDelta(undefined)).toBe(METRIC_COLOR.neutral);
    expect(colorForDelta(Number.NaN)).toBe(METRIC_COLOR.neutral);
  });
});

describe("colorForRiskState (B042 banner palette)", () => {
  it("maps each state onto the shared emerald / amber / destructive palette", () => {
    expect(colorForRiskState("green")).toBe(RISK_STATE_STYLES.green);
    expect(colorForRiskState("yellow")).toBe(RISK_STATE_STYLES.yellow);
    expect(colorForRiskState("red")).toBe(RISK_STATE_STYLES.red);
    // Green uses emerald (not the old ad-hoc green-700/950); red uses destructive.
    expect(RISK_STATE_STYLES.green).toContain("emerald");
    expect(RISK_STATE_STYLES.green).not.toContain("green-700");
    expect(RISK_STATE_STYLES.yellow).toContain("amber");
    expect(RISK_STATE_STYLES.red).toContain("destructive");
  });
});

describe("colorForDrawdown (B042 per-sleeve severity)", () => {
  const THRESHOLD = 0.08;
  it("steady < 5% green, mid amber, at/above per-sleeve threshold red", () => {
    expect(colorForDrawdown(0.01, THRESHOLD)).toBe(METRIC_COLOR.positive);
    expect(colorForDrawdown(0.049, THRESHOLD)).toBe(METRIC_COLOR.positive);
    expect(colorForDrawdown(0.05, THRESHOLD)).toBe(METRIC_COLOR.warning);
    expect(colorForDrawdown(0.079, THRESHOLD)).toBe(METRIC_COLOR.warning);
    expect(colorForDrawdown(0.08, THRESHOLD)).toBe(METRIC_COLOR.negative);
    expect(colorForDrawdown(0.2, THRESHOLD)).toBe(METRIC_COLOR.negative);
  });

  it("null / undefined / NaN → neutral", () => {
    expect(colorForDrawdown(null, THRESHOLD)).toBe(METRIC_COLOR.neutral);
    expect(colorForDrawdown(undefined, THRESHOLD)).toBe(METRIC_COLOR.neutral);
    expect(colorForDrawdown(Number.NaN, THRESHOLD)).toBe(METRIC_COLOR.neutral);
  });
});

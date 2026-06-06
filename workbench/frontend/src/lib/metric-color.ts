/**
 * B040 F002 — Robinhood-style metric colour coding.
 *
 * Maps a metric value to a Tailwind text-colour class. Colour is an
 * at-a-glance aid only (never a decision/execution signal — the workbench
 * is research-only). Thresholds are the spec §4.2 initial defaults and may
 * be tuned. Volatility / Turnover are intentionally neutral (lower-is-
 * steadier, but "good/bad" is context-dependent).
 */

export type MetricKey =
  | "sharpe"
  | "sortino"
  | "calmar"
  | "cagr"
  | "maxDrawdown"
  | "volatility"
  | "turnover";

export const METRIC_COLOR = {
  positive: "text-emerald-400",
  warning: "text-amber-300",
  negative: "text-red-400",
  neutral: "text-foreground",
} as const;

export type MetricColor = (typeof METRIC_COLOR)[keyof typeof METRIC_COLOR];

/** Return the Tailwind text-colour class for a metric value.
 * Null / undefined / NaN → neutral (the "—" empty cell). */
export function colorForMetric(key: MetricKey, value: number | null | undefined): MetricColor {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return METRIC_COLOR.neutral;
  }
  switch (key) {
    // Ratio metrics: >=1 strong, 0–1 modest, <0 poor.
    case "sharpe":
    case "sortino":
    case "calmar":
      if (value >= 1) return METRIC_COLOR.positive;
      if (value >= 0) return METRIC_COLOR.warning;
      return METRIC_COLOR.negative;
    // CAGR: positive green, negative red (zero neutral).
    case "cagr":
      if (value > 0) return METRIC_COLOR.positive;
      if (value < 0) return METRIC_COLOR.negative;
      return METRIC_COLOR.neutral;
    // Max drawdown is negative; closer to 0 is better.
    case "maxDrawdown":
      if (value > -0.05) return METRIC_COLOR.positive;
      if (value >= -0.2) return METRIC_COLOR.warning;
      return METRIC_COLOR.negative;
    // Neutral — no colour judgement.
    case "volatility":
    case "turnover":
      return METRIC_COLOR.neutral;
    default:
      return METRIC_COLOR.neutral;
  }
}

/** B041 — colour for a target/current weight delta (rebalance direction):
 * positive (buy more) green, negative (trim) red, flat neutral. Reuses the
 * shared METRIC_COLOR palette. Colour is an at-a-glance rebalance hint only,
 * not a buy/sell instruction (the workbench is research-only). */
export function colorForDelta(value: number | null | undefined): MetricColor {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return METRIC_COLOR.neutral;
  }
  if (value > 0) return METRIC_COLOR.positive;
  if (value < 0) return METRIC_COLOR.negative;
  return METRIC_COLOR.neutral;
}

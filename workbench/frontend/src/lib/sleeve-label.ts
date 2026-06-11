/**
 * B054 fix-round 1 — Simplified-Chinese display labels for sleeve ids and
 * report kinds. The backend keeps the raw ids (``satellite_us_quality``,
 * ``investment``) as stable data keys; these helpers translate them at the
 * presentation layer so no English identifier leaks onto user-facing pages.
 * Unknown ids pass through unchanged (better a raw id than a crash).
 */

const SLEEVE_LABELS: Record<string, string> = {
  master: "旗舰组合",
  momentum: "动量核心",
  risk_parity: "风险平价",
  satellite_us_quality: "美股质量卫星",
  satellite_hk_china: "港股中概卫星",
  regime: "市场态势自适应",
  regime_adaptive: "市场态势自适应",
  unclassified: "未分类",
};

export function sleeveLabel(sleeve: string): string {
  return SLEEVE_LABELS[sleeve] ?? sleeve;
}

const REPORT_KIND_LABELS: Record<string, string> = {
  investment: "投资报告",
  backtest: "回测报告",
  research: "研究报告",
};

export function reportKindLabel(kind: string): string {
  return REPORT_KIND_LABELS[kind] ?? kind;
}

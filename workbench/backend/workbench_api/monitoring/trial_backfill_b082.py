"""B082 F002 — 红利低波 defensive-sleeve OOS card + backtest trials (backfill source).

Single source of truth for the two DB seeds F002 lands (three-同源 with migration 0037
+ the bootstrap CLI, mirroring B081):

* ``CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT`` — the ``oos_verification_card`` row for the new
  ``cn_dividend_lowvol`` strategy (``validated=False``, ``oos_result="mixed"``). F003
  builds the precompute producer that READS this card; F002 only lands the row + the
  in-code constant (the card values live here, NOT in a precompute module, because no
  producer exists yet). A backend guard test asserts the migration seeds byte-identical
  to this constant.
* ``B082_TRIALS`` — the 6 backtest configs actually run (DSR ``N`` accounting): the
  primary index-TR strategy + buy-hold baseline, and the implementable ETF strategy +
  baseline at BOTH 10万 / 100万 capital. Metrics are transcribed VERBATIM from the run
  (``data/research/b082/backtest_results.json`` → report
  ``docs/test-reports/B082-F002-backtest.md``; the b082 snapshot is git-ignored and NOT
  on the deploy host, so the numbers are embedded as a static constant like B081).

★ Honest headline (spec §3 不变量 / 防守腿验收): the three-tier 利差 rule delivers
DRAWDOWN protection (its design goal — full-cycle MaxDD −66%→−41%) but NO return uplift
(CAGR 10.6%→7.5%); the 2022/2024 defensive edge comes mostly from the dividend-lowvol
INSTRUMENT itself, not the rule. "No return增量" is a valid defensive-sleeve finding.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from workbench_api.monitoring.trial_backfill import _window_dates, trial_id

CN_DIVIDEND_LOWVOL_STRATEGY_ID = "cn_dividend_lowvol"

# Fixed stamp so re-runs (bootstrap upsert + the auto-deploy data-migration) are
# byte-identical no-ops (mirrors TRIAL_BACKFILL_STAMP / B081_TRIAL_STAMP).
B082_TRIAL_STAMP = datetime(2026, 7, 4, tzinfo=UTC)

# --------------------------------------------------------------------------- #
# OOS red card (8-key ResearchCaveat dict; drop-in for the DB row's value columns)
# --------------------------------------------------------------------------- #
CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT: dict[str, Any] = {
    "validated": False,
    # mixed: the rule cuts tail drawdown (defensive win) but adds NO return, and the
    # unadjusted-ETF implementable layer is even negative — a genuinely two-sided result.
    "oos_result": "mixed",
    "oos_cagr_range": "TR指数OOS: 策略+6.3% vs 持有+8.5%（规则减回撤不增收益）",
    "headline_zh": (
        "未经样本外验证：红利低波防守腿——三档利差规则（股息率−十年国债 ≥2.5%满配/"
        "1.5-2.5%半配/<1.5%低配；阈值 spec 先验、禁回测扫参）。21.5y 全收益指数口径下，"
        "规则把全周期最大回撤 −66%→−41%（防守腿设计目标=削尾部），但**不增收益**"
        "（CAGR 10.6%→7.5%，OOS 8.5%→6.3%）。2022 回撤 −12% vs HS300 −29%、2024-02 −5.4%——"
        "但这两窗口防守主要来自红利低波品种本身、非利差规则（该期满配）。可实施 ETF 层"
        "（512890 未复权价、含成本）10万≈100万本金（单一低价 ETF 无 B081 容量下限）。"
        "2025 AI 牛跑输：+7.9% vs HS300 +21.2%。研究态、不可配资。"
    ),
    "headline_en": (
        "Unvalidated OOS: dividend-low-vol defensive sleeve — three-tier yield-spread rule "
        "(dividend-yield − 10Y: ≥2.5% full / 1.5-2.5% half / <1.5% low; thresholds "
        "spec-prior, never backtest-tuned). Over 21.5y (total-return index) the rule cuts "
        "full-cycle max drawdown −66%→−41% but adds NO return (CAGR "
        "10.6%→7.5%, OOS 8.5%→6.3%); the 2022/2024-02 defence is mostly the instrument, not "
        "the rule. ETF layer (512890, unadjusted): 100k ≈ 1M CNY (no B081 capacity floor). "
        "2025 lagged the AI rally. Research-only, unfunded."
    ),
    "detail_zh": (
        "advisory-only：系统只给建议，不自动下单、不预测收益。防守腿验收重点是回撤控制"
        "而非收益，「规则无收益增量」是合法结论。按它交易风险自负。"
    ),
    "detail_en": (
        "Advisory-only: the system only suggests; it does not auto-trade or predict "
        "returns. A defensive sleeve is judged on drawdown control, not return — 'no "
        "return uplift from the rule' is a valid finding. Trading on it is at your own risk."
    ),
    "backtest_ref": "docs/test-reports/B082-F002-backtest.md",
}

# --------------------------------------------------------------------------- #
# backtest trials (6 configs actually run — verbatim metrics)
# --------------------------------------------------------------------------- #
_SOURCE_REF = "docs/test-reports/B082-F002-backtest.md"

# (params, universe, window, oos_split, metrics_summary, verdict)
_RAW: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "三档利差策略 (primary, index TR, no cost, fractional, monthly T+1)",
        "H20269 中证红利低波动全收益指数 (TR, 2005起, 无成本口径)",
        "2005-01-01 -> 2026-07-03",
        "WF 70/30 + CPCV-lite K4 (交错, 非全CPCV)",
        "CAGR 7.49% / Sharpe 0.590 / MaxDD -40.5% / OOS_CAGR 6.34% / OOS_Sharpe 0.493 / "
        "OOS_DD -18.1% / turnover 42.95 / rebal 166 / CPCV-lite_K4 [-5.8%,16.8%,14.1%,8.5%] "
        "/ DD2022 -12.4% / DD2024Feb -5.4% (规则削尾部回撤但不增收益 vs 持有)",
        "INCONCLUSIVE",
    ),
    (
        "买入持有基线 (primary, index TR, no cost)",
        "H20269 中证红利低波动全收益指数 (TR, 2005起, 无成本口径)",
        "2005-01-01 -> 2026-07-03",
        "WF 70/30",
        "CAGR 10.64% / Sharpe 0.579 / MaxDD -66.2% / OOS_CAGR 8.54% / OOS_Sharpe 0.584 / "
        "turnover 1.0 / rebal 1 / DD2022 -13.5% / DD2024Feb -5.4% (buy-and-hold baseline)",
        "NA",
    ),
    (
        "三档利差策略 @10万 (implementable, 512890 ETF, cost 2.5+5bp 无印花税, 100股/手, 0.5%费)",
        "512890 中证红利低波动 ETF (sina 未复权价, 2019起)",
        "2019-01-18 -> 2026-07-03",
        "full-sample (implementability/cost layer)",
        "CAGR -3.30% / MaxDD -59.1% / Sharpe 0.016 / turnover 6.71 / rebal 20 "
        "/ DD2022 -12.4% / DD2024Feb -5.2% (未复权价低估总收益~4.5%/yr; 收益口径以TR指数为准)",
        "INCONCLUSIVE",
    ),
    (
        "三档利差策略 @100万 (implementable, 512890 ETF, 同上, 容量对照)",
        "512890 中证红利低波动 ETF (sina 未复权价, 2019起)",
        "2019-01-18 -> 2026-07-03",
        "full-sample (implementability/cost layer)",
        "CAGR -3.30% / MaxDD -59.1% / Sharpe 0.016 / turnover 6.71 / rebal 20 "
        "(≈ 10万本金: 单一低价ETF无B081容量下限)",
        "INCONCLUSIVE",
    ),
    (
        "买入持有基线 @10万 (implementable, 512890 ETF, cost+手数+费)",
        "512890 中证红利低波动 ETF (sina 未复权价, 2019起)",
        "2019-01-18 -> 2026-07-03",
        "full-sample (implementability/cost layer)",
        "CAGR 0.27% / MaxDD -59.3% / Sharpe 0.183 / turnover 1.38 / rebal 5 "
        "/ DD2022 -14.2% (buy-and-hold baseline @100k, ETF未复权)",
        "NA",
    ),
    (
        "买入持有基线 @100万 (implementable, 512890 ETF, 容量对照)",
        "512890 中证红利低波动 ETF (sina 未复权价, 2019起)",
        "2019-01-18 -> 2026-07-03",
        "full-sample (implementability/cost layer)",
        "CAGR 0.27% / MaxDD -59.3% / Sharpe 0.183 / turnover 1.38 / rebal 5 "
        "(≈ 10万本金: 单一低价ETF无容量下限)",
        "NA",
    ),
)


def _build(entry: tuple[str, str, str, str, str, str]) -> dict[str, Any]:
    params, universe, window, oos_split, metrics, verdict = entry
    start, end = _window_dates(window)
    return {
        "id": trial_id("B082", CN_DIVIDEND_LOWVOL_STRATEGY_ID, params, universe, window),
        "batch": "B082",
        "strategy_id": CN_DIVIDEND_LOWVOL_STRATEGY_ID,
        "params": {"description": params, "window": window},
        "universe": universe,
        "window_start": start,
        "window_end": end,
        "oos_split": oos_split,
        "metrics": {"summary": metrics},
        "verdict": verdict,
        "source_ref": _SOURCE_REF,
    }


B082_TRIALS: tuple[dict[str, Any], ...] = tuple(_build(e) for e in _RAW)


__all__ = [
    "B082_TRIALS",
    "B082_TRIAL_STAMP",
    "CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT",
    "CN_DIVIDEND_LOWVOL_STRATEGY_ID",
]

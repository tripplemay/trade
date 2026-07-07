"""B106 F002 — Master 组合层 uplift A/B as a trial-registry entry (DSR N).

A portfolio-layer A/B (add the cn_dividend_lowvol defensive sleeve to the Master
barbell + re-weight the sleeves) is a distinct CONFIG tried → counts toward the
Deflated Sharpe ``N``. Metrics from docs/test-reports/B106-portfolio-uplift-ab.md.
Migration 0042 lands it on deploy (alembic, never bootstrap — B080 F005); bootstrap
seeds it for local-dev lockstep.

★ Verdict NO-GO: under a USD-unified 口径 the CNY defensive leg is (mildly POSITIVELY)
correlated with the USD/global attack sleeves — the B082 negative correlation was
A股-internal (vs A股 momentum), which this book does not hold — and FX conversion
inflates its vol/drawdown. No barbell scheme clears the ΔSharpe≥0.15 & ΔMaxDD≥3pp gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from workbench_api.monitoring.trial_backfill import _window_dates, trial_id

_STRATEGY_ID = "master_portfolio_defensive_barbell"
_UNIVERSE = (
    "Master 5-sleeve barbell (4 USD attack: momentum/risk_parity/us_quality/hk_china "
    "+ cn_dividend_lowvol CNY defensive); USD-unified 口径, FX-converted defensive leg"
)
_WINDOW = "2015-09-30 -> 2026-04-30"
_PARAMS = (
    "组合层 A/B 5 方案 (sleeve-return level, 月度, 116 月对齐窗口, USD 统一): "
    "①现状 4-sleeve fixed 40/30/20/10 ②barbell+fixed(防守腿 20%, 进攻×0.8) "
    "③barbell+risk_parity(滚动 inverse-vol) ④barbell+hrp ⑤barbell+vol_target(8%). "
    "权重派生复用 trade.portfolio.master.resolve_sleeve_weights; 防守腿 CNY→USD 汇率换算; 禁扫参"
)
_METRICS = (
    "Sharpe: ①1.222(基线) ②1.141 ③1.234 ④1.168 ⑤1.092; "
    "MaxDD: ①−8.3% ②−8.1% ③−7.0% ④−6.7% ⑤−8.1%; "
    "CAGR: ①10.46% ②9.33% ③7.93% ④6.91% ⑤8.24%. "
    "最优 ③ risk_parity ΔSharpe 仅 +0.012 (<0.15 门槛) 且拖 CAGR −2.5pp. "
    "★红利低波 vs 进攻腿相关性 USD +0.20~+0.48 / CNY 原生 +0.11~+0.41 (弱正, 非负相关) — "
    "spec 的负相关是 vs A股动量(本组不持); FX 换算把防守腿波动抬到 15.8%、MaxDD −31.8%. "
    "★裁定 NO-GO 保持现状: 跨市场+跨币种双错配→分散前提不成立, 加防守腿纯稀释高 Sharpe 进攻腿"
)
_SOURCE_REF = "docs/test-reports/B106-portfolio-uplift-ab.md"

B106_TRIAL_STAMP = datetime(2026, 7, 7, tzinfo=UTC)


def _build() -> tuple[dict[str, Any], ...]:
    start, end = _window_dates(_WINDOW)
    return (
        {
            "id": trial_id("B106", _STRATEGY_ID, _PARAMS, _UNIVERSE, _WINDOW),
            "batch": "B106",
            "strategy_id": _STRATEGY_ID,
            "params": {"description": _PARAMS, "window": _WINDOW},
            "universe": _UNIVERSE,
            "window_start": start,
            "window_end": end,
            "oos_split": "sleeve-return A/B, 116 月对齐窗口 (滚动权重派生, 无 look-ahead)",
            "metrics": {"summary": _METRICS},
            "verdict": "NO_GO",
            "source_ref": _SOURCE_REF,
        },
    )


B106_TRIALS: tuple[dict[str, Any], ...] = _build()

"""B084 F002 — the A股 ETF 时序趋势 first-look as a trial-registry entry (DSR N).

A LEAN-GO first-look is a CONFIG tried → counts toward the Deflated Sharpe ``N`` (B077/
B083 precedent). Metrics transcribed from docs/test-reports/B084-etf-trend-ic.md.
Migration 0039 lands this on deploy (alembic upgrade, never bootstrap — B080 F005); the
bootstrap CLI seeds it too for local-dev lockstep.
"""

from __future__ import annotations

from typing import Any

from workbench_api.monitoring.trial_backfill import (
    TRIAL_BACKFILL_STAMP,
    _window_dates,
    trial_id,
)

_STRATEGY_ID = "cn_etf_trend_first_look"
_UNIVERSE = "A股 宽基/红利 ETF (510300/510500/588000/512890/159915)"
_WINDOW = "2011-12-09 -> 2026-07-03"
_PARAMS = (
    "ETF 时序趋势 first-look: 月末 12-月绝对动量>0→持有否则退现金 (先验禁扫参), 月度调仓; "
    "对照等权买入持有; 原始价(Sina 非复权)"
)
_METRICS = (
    "趋势 full CAGR 17.9%/Sharpe 0.566/MaxDD -45.9% vs 买入持有 14.2%/0.478/-53.2%; "
    "趋势全面胜(收益+夏普+回撤); 2022熊市趋势-6.0% vs 持有-8.4%(防守减亏). "
    "★caveat: OOS Sharpe 1.14>full 0.566=窗口落位嫌疑(OOS含2022熊市); 样本小(5 ETF/163月); 非复权. "
    "LEAN-GO=推荐独立策略批严验(CPCV+更多ETF+复权+更长OOS)再判可配"
)
_SOURCE_REF = "docs/test-reports/B084-etf-trend-ic.md"


def _build() -> tuple[dict[str, Any], ...]:
    start, end = _window_dates(_WINDOW)
    return (
        {
            "id": trial_id("B084", _STRATEGY_ID, _PARAMS, _UNIVERSE, _WINDOW),
            "batch": "B084",
            "strategy_id": _STRATEGY_ID,
            "params": {"description": _PARAMS, "window": _WINDOW},
            "universe": _UNIVERSE,
            "window_start": start,
            "window_end": end,
            "oos_split": "first-look WF 70/30 (trend vs buy-hold, 分窗口 2022/2024H1)",
            "metrics": {"summary": _METRICS},
            # LEAN-GO maps to INCONCLUSIVE (valid verdict set): a real positive/defensive
            # lean, but not conclusively validated (OOS window artifact) — needs the
            # rigorous follow-up batch before a true GO. The metrics carry the lean.
            "verdict": "INCONCLUSIVE",
            "source_ref": _SOURCE_REF,
        },
    )


B084_TRIALS: tuple[dict[str, Any], ...] = _build()
B084_TRIAL_STAMP = TRIAL_BACKFILL_STAMP

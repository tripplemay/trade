"""B085 F001 — residual-momentum-vs-raw IC screen as a trial-registry entry (DSR N).

A first-look screen (residual vs raw momentum rank-IC) is a CONFIG tried → counts toward
the Deflated Sharpe ``N`` (B083/B084 precedent). Metrics from
docs/test-reports/B085-residual-vs-raw-ic-screen.md. Migration 0040 lands it on deploy
(alembic, never bootstrap — B080 F005); bootstrap seeds it for local-dev lockstep.

The full engine A/B was deferred (it requires modifying the frozen cn_attack flagship —
a hard-boundary governance decision); this screen stands alone as the F001 first-look.
"""

from __future__ import annotations

from typing import Any

from workbench_api.monitoring.trial_backfill import (
    TRIAL_BACKFILL_STAMP,
    _window_dates,
    trial_id,
)

_STRATEGY_ID = "cn_attack_residual_momentum_screen"
_UNIVERSE = "B070 去偏 PIT 宇宙 (cn_attack)"
_WINDOW = "2019-04-01 -> 2026-07-03"
_PARAMS = (
    "残差 vs 裸动量 rank-IC 前置筛: 单因子残差动量(日收益对等权市场收益 rolling β=cov/var 窗252 "
    "取残差, 残差过去[t-21-126,t-21]累计) vs 同窗裸动量; forward-return 月度 rank-IC; 先验禁扫参"
)
_METRICS = (
    "残差 IC 0.0108(t=0.45 弱) vs 裸 IC -0.0009(t=-0.04 ~零, 证实A股裸动量弱); "
    "改进配对 delta +0.0118 t=1.98(borderline 显著, 恰低于2.0). "
    "★裁定 弱但真实方向支持: 残差>裸(borderline)但残差绝对IC<|IC|>0.03 GO门槛 → 引擎A/B值得做但期望低. "
    "★caveat(避B084过度乐观): t=1.98非铁证; b070大盘宇宙偏差(相对比较稳健). 完整引擎A/B deferred(需触冻结flagship决策)"
)
_SOURCE_REF = "docs/test-reports/B085-residual-vs-raw-ic-screen.md"


def _build() -> tuple[dict[str, Any], ...]:
    start, end = _window_dates(_WINDOW)
    return (
        {
            "id": trial_id("B085", _STRATEGY_ID, _PARAMS, _UNIVERSE, _WINDOW),
            "batch": "B085",
            "strategy_id": _STRATEGY_ID,
            "params": {"description": _PARAMS, "window": _WINDOW},
            "universe": _UNIVERSE,
            "window_start": start,
            "window_end": end,
            "oos_split": "first-look 月度 rank-IC (残差 vs 裸动量, 51 月度点)",
            "metrics": {"summary": _METRICS},
            "verdict": "INCONCLUSIVE",
            "source_ref": _SOURCE_REF,
        },
    )


B085_TRIALS: tuple[dict[str, Any], ...] = _build()
B085_TRIAL_STAMP = TRIAL_BACKFILL_STAMP

"""B083 F002 — the PEAD 业绩预告 first-look IC as a trial-registry entry (DSR N).

An INCONCLUSIVE first-look is still a CONFIG tried — recorded so the Deflated Sharpe
``N`` counts it honestly (B077 precedent: INCONCLUSIVE IC trials are registered too).
Metrics transcribed from docs/test-reports/B083-pead-first-look-ic.md. Migration 0038
lands this on deploy (alembic upgrade, never bootstrap — the B080 F005 lesson); the
bootstrap CLI seeds it too for local-dev lockstep.
"""

from __future__ import annotations

from typing import Any

from workbench_api.monitoring.trial_backfill import (
    TRIAL_BACKFILL_STAMP,
    _window_dates,
    trial_id,
)

_STRATEGY_ID = "cn_pead_first_look"
_UNIVERSE = "B070 survivorship-free de-biased PIT ∩ 业绩预告事件"
_WINDOW = "2019-01-14 -> 2025-04-30"
_PARAMS = (
    "PEAD first-look: 预告净利润 surprise (vs 去年同期, 先验禁扫参) × B070 去偏 PIT 宇宙; "
    "事件日=公告日(PIT), 进场 T+1; naive 口径 (预告非实际快报, SUE 用去年同期)"
)
_METRICS = (
    "rank-IC(可执行) N1 +0.021 / N5 -0.021 / N10 -0.076 / N20 -0.057 (8172 事件); "
    "弱 pop + reversal, 非 PEAD 正向 drift, 跨 horizon 不同号不单调 → INCONCLUSIVE. "
    "caveats: B070=cn_attack 动量大盘宇宙(事件覆盖仅 23%, PEAD 最强在小盘) / 预告≠实际财报快报 / "
    "SUE 用去年同期非分析师一致预期 — 均系统性低估 edge, 不等于 PEAD 无效"
)
_SOURCE_REF = "docs/test-reports/B083-pead-first-look-ic.md"


def _build() -> tuple[dict[str, Any], ...]:
    start, end = _window_dates(_WINDOW)
    return (
        {
            "id": trial_id("B083", _STRATEGY_ID, _PARAMS, _UNIVERSE, _WINDOW),
            "batch": "B083",
            "strategy_id": _STRATEGY_ID,
            "params": {"description": _PARAMS, "window": _WINDOW},
            "universe": _UNIVERSE,
            "window_start": start,
            "window_end": end,
            "oos_split": "first-look forward-return rank-IC N1/N5/N10/N20",
            "metrics": {"summary": _METRICS},
            "verdict": "INCONCLUSIVE",
            "source_ref": _SOURCE_REF,
        },
    )


B083_TRIALS: tuple[dict[str, Any], ...] = _build()
B083_TRIAL_STAMP = TRIAL_BACKFILL_STAMP

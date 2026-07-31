"""B111 F004 fix-round — paper cost constants drift-guard.

The paper engine (workbench side) must never import ``trade`` on its own
path (spec §4.3 / §12.10), so the unified caliber lives in TWO places by
design: ``trade/backtest/execution_caliber.py`` (canonical, backtest side)
and ``workbench_api/paper/service.py`` (paper side). This guard pins them
in lockstep — the same pattern as the ETF_UNIVERSE drift-guard — so one
side can never drift without the other going red.
"""

from __future__ import annotations

from trade.backtest.execution_caliber import (  # type: ignore[import-untyped]
    UNIFIED_COST_BPS,
    UNIFIED_SLIPPAGE_BPS,
)

from workbench_api.paper.service import DEFAULT_FEE_BPS, DEFAULT_SLIPPAGE_BPS


def test_paper_fee_matches_unified_caliber() -> None:
    assert DEFAULT_FEE_BPS == UNIFIED_COST_BPS == 5.0
    assert DEFAULT_SLIPPAGE_BPS == UNIFIED_SLIPPAGE_BPS == 5.0

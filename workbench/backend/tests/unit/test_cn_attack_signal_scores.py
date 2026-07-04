"""B080 F002 — cn_attack precompute forward-accumulates raw signal_scores.

The producer writes the raw composite factor score per selected name into
``master_meta["signal_scores"]`` (top-N by score) so the monitoring rolling-IC can
later key off the true signal. Pure added meta key — empty when the live target
carries no scores (a hold-day / pre-B080 fixture), which is byte-identical to before.
"""

from __future__ import annotations

from datetime import date

from workbench_api.strategy_modes.cn_attack_precompute import _build_target_result
from workbench_api.strategy_modes.registry import CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID

_AS_OF = date(2026, 7, 3)


def _live(signal_scores: dict[str, float]) -> object:
    from trade.backtest.cn_attack_momentum_quality.live import (  # type: ignore[import-untyped]
        CnAttackLiveTarget,
    )

    return CnAttackLiveTarget(
        as_of_date=_AS_OF,
        signal_date=_AS_OF,
        factor_variant="pure_momentum",
        target_weights={"600519.SH": 0.5, "000858.SZ": 0.5},
        cash_weight=0.0,
        rebalanced=True,
        profit_take=(),
        would_be_turnover=0.1,
        no_trade_band=0.20,
        top_n=2,
        signal_scores=signal_scores,
    )


def test_signal_scores_surface_topn_sorted() -> None:
    live = _live({"600519.SH": 0.02, "000858.SZ": 0.05, "300750.SZ": 0.09})
    result = _build_target_result(
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum", "real", live
    )
    scores = result.meta["signal_scores"]
    # top_n=2 → only the two highest scores, sorted descending.
    assert list(scores) == ["300750.SZ", "000858.SZ"]
    assert scores["300750.SZ"] == 0.09


def test_signal_scores_empty_when_absent() -> None:
    result = _build_target_result(
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum", "real", _live({})
    )
    assert result.meta["signal_scores"] == {}

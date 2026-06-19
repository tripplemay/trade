"""B070 F003 — unit tests for the survivorship-bias verdict logic.

The PIT-vs-control comparison's numbers come from the real backtest (run on the
research data root), but the verdict MAPPING — does the de-biased strategy survive?
(spec §0) — is deterministic and must be locked so the research conclusion is graded
by a stable rule. No network / no backtest here.
"""

from __future__ import annotations

import pytest

from scripts.research.b070_survivorship_comparison import judge


def _metrics(
    *, oos_cagr: float, oos_sharpe: float, rebalances: int = 20, full_cagr: float = 0.3
) -> dict:
    return {
        "rebalance_count": rebalances,
        "full_cagr": full_cagr,
        "oos_cagr": oos_cagr,
        "oos_sharpe": oos_sharpe,
    }


def test_survives_when_pit_oos_positive_cagr_and_sharpe() -> None:
    pit = _metrics(oos_cagr=0.18, oos_sharpe=0.9)
    control = _metrics(oos_cagr=0.42, oos_sharpe=1.6)
    result = judge(pit, control)
    assert result["verdict"] == "SURVIVES_DEBIASING"
    # bias = control - pit
    assert result["survivorship_bias_oos_cagr"] == pytest.approx(0.24)
    assert result["survivorship_bias_oos_sharpe"] == pytest.approx(0.7)


def test_collapses_when_pit_oos_cagr_nonpositive() -> None:
    pit = _metrics(oos_cagr=-0.05, oos_sharpe=0.3)
    control = _metrics(oos_cagr=0.42, oos_sharpe=1.6)
    assert judge(pit, control)["verdict"] == "COLLAPSES_DEBIASING"


def test_collapses_when_pit_oos_sharpe_nonpositive() -> None:
    pit = _metrics(oos_cagr=0.04, oos_sharpe=-0.1)
    control = _metrics(oos_cagr=0.42, oos_sharpe=1.6)
    assert judge(pit, control)["verdict"] == "COLLAPSES_DEBIASING"


def test_inconclusive_when_pit_degenerate() -> None:
    pit = _metrics(oos_cagr=0.0, oos_sharpe=0.0, rebalances=0, full_cagr=0.0)
    control = _metrics(oos_cagr=0.42, oos_sharpe=1.6)
    assert judge(pit, control)["verdict"] == "INCONCLUSIVE"


def test_bias_can_be_negative_when_debiasing_helps() -> None:
    # de-biasing could in principle RAISE returns (unlikely but the math is honest)
    pit = _metrics(oos_cagr=0.30, oos_sharpe=1.2)
    control = _metrics(oos_cagr=0.20, oos_sharpe=0.8)
    result = judge(pit, control)
    assert result["verdict"] == "SURVIVES_DEBIASING"
    assert result["survivorship_bias_oos_cagr"] == pytest.approx(-0.10)

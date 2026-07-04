"""B081 F004 — the 8 engine-fidelity A/B groups as trial-registry entries.

The B081 A/B (scripts/research/b081_engine_fidelity_ab.py) runs 8 switch-combo
configs on the B070 de-biased PIT universe. Each group is a distinct CONFIG tried, so
each is registered as a trial (DSR ``N`` accounting) — the metrics are transcribed
VERBATIM from the A/B report (source_ref points at it). The ``old_all_off`` group
bit-level reproduces the B070 signoff (a reproducibility proof, not a new config).

Numbers are embedded as a static constant (``_AB_METRICS``) — the deploy-time
data-migration imports this module and the b070 data is NOT on the deploy host, so the
metrics can't be read from the run JSON at migration time. A guard test asserts the
embedded metrics match the committed run JSON.
"""

from __future__ import annotations

from typing import Any

from workbench_api.monitoring.trial_backfill import (
    TRIAL_BACKFILL_STAMP,
    _window_dates,
    trial_id,
)

_UNIVERSE = "B070 survivorship-free de-biased PIT"
_WINDOW = "2019-04-01 -> 2026-06-24"
_OOS_SPLIT = "WF 70/30"
_SOURCE_REF = "docs/test-reports/B081-engine-fidelity-ab.md"
_STRATEGY_ID = "cn_attack_pure_momentum"

# (label, human description) — the fixed A/B design, independent of the numbers.
_GROUPS: tuple[tuple[str, str], ...] = (
    ("old_all_off", "旧口径: all switches off, stamp 10bp — pre-B081 (bit-level == B070 signoff)"),
    ("only_lot_rounding", "+ lot_rounding only (100股/手取整, remainder→cash), stamp 10bp"),
    ("only_partial_rebalance", "+ partial_rebalance only (band部分调仓 A, 0.5%), stamp 10bp"),
    ("only_suspension_halt", "+ suspension_halt only (停牌 no-trade, frozen), stamp 10bp"),
    ("only_delist_liquidation", "+ delist_liquidation only (退市清仓 recovery 1.0), stamp 10bp"),
    ("only_price_limit_gating", "+ price_limit_gating only (涨跌停禁买卖), stamp 10bp"),
    ("new_all_on", "全on 新基线: all fixes + stamp 5bp — B081 引擎修真后口径"),
    ("new_all_on_recovery_0p5", "全on + delist recovery 0.5 (haircut sensitivity), stamp 5bp"),
)

# Metrics transcribed VERBATIM from the A/B run (scripts/research/b081_engine_fidelity_ab.py
# → docs/test-reports/B081-engine-fidelity-ab.md). The headline honest finding: realistic
# 100-lot rounding on the *ST-heavy PIT turns the strategy NEGATIVE (OOS +28.4% → -14.7%),
# so the B070 edge was substantially a fractional-share artifact. F002 (停牌/退市) are
# no-ops here (the book holds liquid names). A backend test guards the registration path.
_AB_METRICS: dict[str, str] = {
    "old_all_off": "CAGR 13.1% / Sharpe 0.559 / MaxDD -58.3% / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / turnover 194 / rebal 639 (bit-level == B070 signoff)",
    "only_lot_rounding": "CAGR -8.6% / Sharpe -0.653 / MaxDD -50.7% / OOS_CAGR -16.0% / OOS_Sharpe -2.162 / turnover 1160 / rebal 1749 (dominant 数字变差: sub-lot *ST skipped + 6x churn)",
    "only_partial_rebalance": "CAGR 20.7% / Sharpe 0.769 / MaxDD -50.2% / OOS_CAGR 32.7% / OOS_Sharpe 1.04 / turnover 236 / rebal 1517 (数字变好: more signal-responsive)",
    "only_suspension_halt": "CAGR 13.1% / Sharpe 0.559 / MaxDD -58.3% / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / turnover 194 / rebal 639 (NO-OP == old: liquid book never halts)",
    "only_delist_liquidation": "CAGR 13.1% / Sharpe 0.559 / MaxDD -58.3% / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / turnover 194 / rebal 639 (NO-OP == old: held names never delist)",
    "only_price_limit_gating": "CAGR 13.1% / Sharpe 0.559 / MaxDD -58.2% / OOS_CAGR 28.9% / OOS_Sharpe 0.939 / turnover 195 / rebal 642 (~no-op, +0.5pp OOS)",
    "new_all_on": "CAGR -6.6% / Sharpe -0.409 / MaxDD -46.9% / OOS_CAGR -14.7% / OOS_Sharpe -1.671 / turnover 1070 / rebal 1749 (B081 修真后: strategy NEGATIVE, lot_rounding dominates)",
    "new_all_on_recovery_0p5": "CAGR -6.6% / Sharpe -0.409 / MaxDD -46.9% / OOS_CAGR -14.7% / OOS_Sharpe -1.671 / turnover 1070 / rebal 1749 (== new_all_on; delist recovery no-op here)",
}


def _build_b081() -> tuple[dict[str, Any], ...]:
    start, end = _window_dates(_WINDOW)
    trials: list[dict[str, Any]] = []
    for label, description in _GROUPS:
        params = f"{label}: {description}"
        metrics = _AB_METRICS.get(label, "PENDING A/B run")
        trials.append(
            {
                "id": trial_id("B081", _STRATEGY_ID, params, _UNIVERSE, _WINDOW),
                "batch": "B081",
                "strategy_id": _STRATEGY_ID,
                "params": {"description": params, "window": _WINDOW},
                "universe": _UNIVERSE,
                "window_start": start,
                "window_end": end,
                "oos_split": _OOS_SPLIT,
                "metrics": {"summary": metrics},
                "verdict": "NA",
                "source_ref": _SOURCE_REF,
            }
        )
    return tuple(trials)


B081_AB_TRIALS: tuple[dict[str, Any], ...] = _build_b081()
B081_TRIAL_STAMP = TRIAL_BACKFILL_STAMP

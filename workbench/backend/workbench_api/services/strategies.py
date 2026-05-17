"""Strategy registry adapter (B022 F007).

The four sleeves the workbench surfaces in Phase 1 mirror the
specs that introduced them. F007's contract is the schema + a stable
strategy id; the actual config / performance data lives in trade/ and
will be wired through in B023 when the master portfolio runner has a
batch-stable API the workbench can call without spawning a subprocess.

For F007 we ship a hand-curated registry that:

* uses the real spec paths under ``docs/specs/`` so the frontend's spec
  button (F007 acceptance — "spec/code 链按钮") resolves via
  ``/api/docs/{path}``;
* uses the most-defensible ``trade/strategies/`` code path so the code
  button does the same;
* points B013-regime-quarterly's ``last_sweep_path`` at the B019 retune
  report (the latest sweep that touched it; threshold=0.11);
* leaves equity / drawdown / turnover series empty — F007 acceptance
  allows the detail panel to render the charts with empty data and
  show the placeholder state. F008's backtest runner is the source for
  populated series, not this registry.
"""

from __future__ import annotations

from workbench_api.schemas.strategies import (
    StrategyDetail,
    StrategyListResponse,
    StrategyProvenance,
    StrategySummary,
)


def _summary(
    *,
    id: str,
    name: str,
    sleeve: str,
    status: str = "active",
    last_sweep_date: str | None = None,
) -> StrategySummary:
    return StrategySummary(
        id=id,
        name=name,
        sleeve=sleeve,
        status=status,
        last_sweep_date=last_sweep_date,
    )


# Single source of truth for the 4 sleeves. Adding a 5th requires a
# spec; B023 is the next batch that can extend this registry.
_REGISTRY: dict[str, tuple[StrategySummary, StrategyProvenance, dict[str, object]]] = {
    "B013-regime-quarterly": (
        _summary(
            id="B013-regime-quarterly",
            name="Regime-Adaptive Multi-Asset (quarterly)",
            sleeve="regime",
            last_sweep_date="2026-05-13",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B013-regime-adaptive-multi-asset-mvp-spec.md",
            code_path="trade/strategies/regime_adaptive",
            last_sweep_path=(
                "docs/test-reports/B019-retune-recommendations-signoff-2026-05-15.md"
            ),
        ),
        {
            "rebalance": "quarterly",
            "activation_threshold": 0.11,
            "note": "B019 retune set activation_threshold=0.11 (was 0.13).",
        },
    ),
    "B014-regime-stress": (
        _summary(
            id="B014-regime-stress",
            name="Regime-Adaptive Stress Validation",
            sleeve="regime",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B014-regime-adaptive-stress-validation-spec.md",
            code_path="trade/strategies/regime_adaptive",
            last_sweep_path=None,
        ),
        {"role": "validation harness for B013 under stress windows."},
    ),
    "B015-regime-active": (
        _summary(
            id="B015-regime-active",
            name="Regime-Adaptive Activation Policy",
            sleeve="regime",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B015-regime-adaptive-activation-policy-spec.md",
            code_path="trade/strategies/regime_adaptive",
            last_sweep_path=None,
        ),
        {"role": "activation policy attached to B013."},
    ),
    "B016-risk-parity-hrp": (
        _summary(
            id="B016-risk-parity-hrp",
            name="Risk Parity HRP",
            sleeve="risk_parity",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B016-risk-parity-hrp-upgrade-spec.md",
            code_path="trade/strategies/risk_parity_hrp.py",
            last_sweep_path=None,
        ),
        {"rebalance": "monthly", "estimator": "HRP"},
    ),
}


def list_strategies() -> StrategyListResponse:
    """Return the 4 sleeves as the workbench's flat list view."""

    return StrategyListResponse(strategies=[entry[0] for entry in _REGISTRY.values()])


def get_strategy(strategy_id: str) -> StrategyDetail | None:
    """Return the detail for one sleeve, or None when the id is unknown."""

    entry = _REGISTRY.get(strategy_id)
    if entry is None:
        return None
    summary, provenance, config = entry
    return StrategyDetail(
        id=summary.id,
        name=summary.name,
        sleeve=summary.sleeve,
        status=summary.status,
        last_sweep_date=summary.last_sweep_date,
        config=config,
        provenance=provenance,
        # F007 accepts empty performance arrays — F008's backtest runner
        # populates them on demand. The frontend renders the chart
        # wrappers with their built-in "no data" surface.
        equity_curve=[],
        drawdown_series=[],
        turnover_heatmap=[],
    )

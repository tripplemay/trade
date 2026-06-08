"""Strategy registry adapter (B022 F007; B046 F002 reconcile).

The registry is the workbench's hand-curated mirror of the canonical
Master Portfolio composition in ``trade/portfolio/master.py``. F007's
contract is the schema + a stable strategy id; the actual config /
performance data lives in ``trade/`` and is surfaced here so the
frontend (which never imports ``trade/*`` directly, to keep the cloud
build slim) has a stable read model.

**B046 F002 — regime reconcile; BL-B011-S2 — hk_china implemented.**
Before B046 the registry surfaced three regime entries (B013/B014/B015)
as ``active`` and was missing two sleeves the Master actually allocates
to: the ``momentum`` core (``global_etf_momentum``, planning_weight 0.40)
and the ``satellite_hk_china`` sleeve (0.10, then a reserved stub).
BL-B011-S2 then implemented the HK-China sleeve (Master 4/4 real). The
Master's real default sleeves are (see
``master.default_master_portfolio_parameters``):

* ``momentum``            → ``global_etf_momentum``    (0.40, implemented)
* ``risk_parity``         → ``risk_parity_vol_target`` (0.30, implemented)
* ``satellite_us_quality``→ ``us_quality_momentum``    (0.20, implemented)
* ``satellite_hk_china``  → ``hk_china_momentum``      (0.10, implemented; BL-B011-S2)
* ``regime_adaptive``     → planning_weight 0.0 (loadable-but-inactive;
  activating it is a future B013 batch — it stays research-state here).

So this registry now lists the four active sleeves plus the regime
entries marked ``status="research"`` (they describe the regime overlay
that ships at zero weight). The registry is the read model, not the
allocator — it does not change any Master weight or activate regime.

The registry also:

* uses the real spec paths under ``docs/specs/`` so the frontend's spec
  button (F007 acceptance — "spec/code 链按钮") resolves via
  ``/api/docs/{path}``;
* uses the most-defensible ``trade/`` code path so the code button does
  the same;
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


# Single source of truth: the registry mirrors trade/portfolio/master.py.
# Order reflects the Master's default sleeves (active core + satellites
# first), then the regime overlay entries (research-state, zero weight).
# Adding a sleeve requires a spec.
_REGISTRY: dict[str, tuple[StrategySummary, StrategyProvenance, dict[str, object]]] = {
    # B046 F002: the Master's core trend engine (momentum sleeve,
    # planning_weight 0.40). It was missing from the pre-B046 registry,
    # which made /api/strategies + downstream sleeve consumers (home
    # breakdown, advisor precompute, news association) blind to the
    # single largest sleeve. strategy_id mirrors master.py's "momentum"
    # sleeve → "global_etf_momentum".
    "B006-global-etf-momentum": (
        _summary(
            id="B006-global-etf-momentum",
            name="Global ETF Momentum / 全球 ETF 动量",
            sleeve="momentum",
            last_sweep_date="2026-05-12",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B006-global-etf-backtest-mvp-spec.md",
            code_path="trade/strategies/global_etf_momentum.py",
            last_sweep_path=(
                "docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md"
            ),
        ),
        {
            "rebalance": "quarterly",
            "top_n": 2,
            "momentum_windows": "periods=3(0.4) periods=6(0.3) periods=9(0.3)",
            "master_strategy_id": "global_etf_momentum",
            "note": (
                "Master core_trend_engine sleeve (planning_weight=0.40). "
                "Scored on real daily prices (Tiingo, B045 data-refresh). "
                "Research-only advisory — not a return forecast."
            ),
        },
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
        {
            "rebalance": "monthly",
            "estimator": "HRP",
            # B046 F002 id reconcile: the Master wires the risk_parity
            # sleeve to strategy_id "risk_parity_vol_target"; this entry
            # is the B016 HRP upgrade of that sleeve. Recorded so the two
            # ids are traceable to the same sleeve.
            "master_strategy_id": "risk_parity_vol_target",
            "note": (
                "Master core_stabilizer sleeve (planning_weight=0.30). "
                "B016 HRP upgrades the risk_parity_vol_target sleeve."
            ),
        },
    ),
    # B025 F005: surfaces the US Quality Momentum satellite sleeve on the
    # /strategies list and detail panels. trade/portfolio/master.py is the
    # canonical wiring point — this registry mirrors it for the workbench
    # frontend (which never imports trade/* directly to keep the cloud
    # build slim).
    "B025-us-quality-momentum": (
        _summary(
            id="B025-us-quality-momentum",
            name="US Quality Momentum / 美股质量动量",
            sleeve="satellite_us_quality",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B025-us-quality-momentum-satellite-spec.md",
            code_path="trade/strategies/us_quality_momentum",
            last_sweep_path=(
                "docs/test-reports/B025-us-quality-momentum-backtest-2024-12-31.md"
            ),
        ),
        {
            "rebalance": "monthly",
            "top_n": 15,
            "max_position_weight": 0.07,
            "max_sector_weight": 0.30,
            "earnings_window_days": 5,
            "factor_weights": (
                "momentum=0.35 quality=0.30 low_vol=0.15 value=0.10 trend=0.10"
            ),
            "note": (
                "B025 satellite_us_quality (planning_weight=0.20). "
                "Scored on real prices (Tiingo) + real SEC EDGAR filings "
                "(B045 data-refresh). Research-only advisory — not a return forecast."
            ),
        },
    ),
    # BL-B011-S2: the HK-China satellite is now an IMPLEMENTED strategy
    # (was the reserved satellite_stub). master.py flipped sleeve_type →
    # implemented + strategy_id "hk_china_momentum" (Master 4/4 real,
    # precompute data_source=real, 0 stub); planning_weight unchanged
    # (0.10). The registry mirrors that — the prior "reserved stub / no
    # strategy implemented / not live market data" note is now stale.
    "B011-satellite-hk-china": (
        _summary(
            id="B011-satellite-hk-china",
            name="HK / China Satellite Momentum / 港股中概卫星动量",
            sleeve="satellite_hk_china",
        ),
        StrategyProvenance(
            spec_path="docs/specs/BL-B011-S2-hk-china-satellite-spec.md",
            code_path="trade/strategies/hk_china_momentum",
            last_sweep_path=(
                "docs/test-reports/BL-B011-S2-hk-china-satellite-signoff-2026-06-08.md"
            ),
        ),
        {
            "sleeve_type": "implemented",
            "planning_weight": 0.10,
            "role_label": "satellite_regional",
            "master_strategy_id": "hk_china_momentum",
            "note": (
                "Master satellite_hk_china sleeve (planning_weight=0.10), "
                "implemented in BL-B011-S2. Trend-scored on the US-listed "
                "HK/China ETF set (MCHI/FXI/KWEB/ASHR) using real daily prices "
                "(Tiingo, B045 data-refresh). Research-only advisory — not a "
                "return forecast."
            ),
        },
    ),
    # B046 F002: regime overlay entries kept as research-state. The
    # Master loads regime_adaptive at planning_weight=0.0 (loadable but
    # inactive — _resolve_child_weights raises if a >0 weight is set), so
    # these describe the overlay that ships at zero weight. Activating
    # regime is a future B013 batch, not this registry's job.
    "B013-regime-quarterly": (
        _summary(
            id="B013-regime-quarterly",
            name="Regime-Adaptive Multi-Asset (quarterly)",
            sleeve="regime",
            status="research",
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
            "master_planning_weight": 0.0,
            "note": (
                "Research-state: Master loads regime_adaptive at weight 0.0 "
                "(inactive). B019 retune set activation_threshold=0.11 "
                "(was 0.13). Activation is a future B013 batch."
            ),
        },
    ),
    "B014-regime-stress": (
        _summary(
            id="B014-regime-stress",
            name="Regime-Adaptive Stress Validation",
            sleeve="regime",
            status="research",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B014-regime-adaptive-stress-validation-spec.md",
            code_path="trade/strategies/regime_adaptive",
            last_sweep_path=None,
        ),
        {
            "role": "validation harness for B013 under stress windows.",
            "master_planning_weight": 0.0,
            "note": "Research-state: regime overlay ships inactive (weight 0.0).",
        },
    ),
    "B015-regime-active": (
        _summary(
            id="B015-regime-active",
            name="Regime-Adaptive Activation Policy",
            sleeve="regime",
            status="research",
        ),
        StrategyProvenance(
            spec_path="docs/specs/B015-regime-adaptive-activation-policy-spec.md",
            code_path="trade/strategies/regime_adaptive",
            last_sweep_path=None,
        ),
        {
            "role": "activation policy attached to B013.",
            "master_planning_weight": 0.0,
            "note": "Research-state: regime overlay ships inactive (weight 0.0).",
        },
    ),
}


def list_strategies() -> StrategyListResponse:
    """Return the registry sleeves as the workbench's flat list view.

    Order mirrors ``trade/portfolio/master.py``: the active core +
    satellite sleeves first, then the research-state regime overlay
    entries (B046 F002 reconcile)."""

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

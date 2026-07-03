"""B057 F001 — the canonical strategy-mode registry.

A *mode* is a strategy presented as a first-class platform citizen: it has its
own target producer, (eventually) its own paper + real account, its own
backtest engine and its own surfaces. Before B057 only the Master Portfolio
was a mode; this registry makes the set parameterised so regime-adaptive — and
any future strategy — is added by appending one :class:`StrategyMode` row,
never by forking the engine / job / page.

The registry is **dependency-free** (stdlib only) so the DB models, repositories
and the request path can import its canonical ids without an import cycle. It is
a read model: it names modes and their wiring keys; it does not score, allocate
or trade.

Honesty (B057 §1 — capability ≠ funding): :attr:`StrategyMode.funding_state`
records whether a mode is actually funded (``"live"`` — the user is trading it)
or research / forward-validation only (``"research"``). The surfaces use this to
mark unvalidated modes "研究态 / 前向验证中" so building the execution capability
never implies the mode is funded.
"""

from __future__ import annotations

from dataclasses import dataclass

# Canonical strategy ids. These strings are the join key across the
# recommendation_snapshot.strategy_id column, the paper_account.strategy_id
# column, the backtest worker _DISPATCH map and this registry. Defined here
# (single source) so the DB layer can import them without depending on the
# heavier modules.
MASTER_STRATEGY_ID = "master_portfolio"
REGIME_STRATEGY_ID = "regime_adaptive"
# B067 F001 — the two CN attack advisory modes (same engine, different factor
# variant). These are NEW strategy ids distinct from the B066 backtest research
# id ``cn_attack_momentum_quality``: that one stays a backtest-only standalone
# research strategy (services.strategies STANDALONE_RESEARCH_STRATEGY_IDS, NOT a
# Master sleeve); these two are first-class *modes* (their own daily target /
# recommendation / account / execution chain), each with an independent account.
CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID = "cn_attack_quality_momentum"
CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID = "cn_attack_pure_momentum"

# Funding states (B057 §1 honesty boundary).
FUNDING_LIVE = "live"  # the user is trading real money in this mode
FUNDING_RESEARCH = "research"  # research / forward-validation only — not funded

# Rebalance cadences (registry metadata; the producer decides its own signal
# dates — see B057 design note on regime monthly vs Master quarterly).
CADENCE_QUARTERLY = "quarterly"
CADENCE_MONTHLY = "monthly"
CADENCE_DAILY = "daily"  # B067 F001 — CN attack daily-monitor / no-trade-band cadence


@dataclass(frozen=True, slots=True)
class StrategyMode:
    """One strategy presented as a first-class platform mode.

    Attributes:
        id: stable mode id used in URLs / API params (e.g. ``"master"``).
        strategy_id: the canonical strategy id used as the join key across
            ``recommendation_snapshot`` / ``paper_account`` / the backtest
            ``_DISPATCH`` (e.g. ``"master_portfolio"``).
        display_name: Chinese display name (self-contained; the surfaces read
            it directly so they do not couple to the strategies-registry).
        target_producer: which job writes this mode's target into the generic
            target layer (a human-readable label, not an import).
        backtest_key: the ``backtest_run.strategy_id`` the worker dispatches on
            (``None`` until a backtest engine is wired — regime gets one in F002).
        cadence: rebalance cadence metadata (Master quarterly, regime monthly).
        funding_state: ``"live"`` or ``"research"`` — see module docstring.
        description: one-line Chinese description for the surfaces.
    """

    id: str
    strategy_id: str
    display_name: str
    target_producer: str
    backtest_key: str | None
    cadence: str
    funding_state: str
    description: str

    @property
    def is_research_state(self) -> bool:
        """True when the mode is not funded (surfaces mark it 研究态)."""

        return self.funding_state != FUNDING_LIVE


# Single source of truth for the platform's modes, in selector order (the live
# flagship first, research modes after). Adding a mode = append one row here
# (plus its target producer + — when funded — its account/execution wiring).
_MODES: tuple[StrategyMode, ...] = (
    StrategyMode(
        id="master",
        strategy_id=MASTER_STRATEGY_ID,
        display_name="旗舰组合",
        target_producer="workbench_api.recommendations.precompute",
        backtest_key=MASTER_STRATEGY_ID,
        cadence=CADENCE_QUARTERLY,
        funding_state=FUNDING_LIVE,
        description="多 sleeve 旗舰组合（季度调仓），当前真实交易模式。",
    ),
    StrategyMode(
        id="regime",
        strategy_id=REGIME_STRATEGY_ID,
        display_name="智能择时组合",
        target_producer="workbench_api.strategy_modes.regime_precompute",
        # B057 F002 wires regime into the backtest worker _DISPATCH under this
        # key; until then a backtest request for regime is "not wired".
        backtest_key=REGIME_STRATEGY_ID,
        # B057 design note: the regime engine's doctrinal sweep cadence (B019)
        # was quarterly for the zero-weight overlay, but the B057 regime *mode*
        # re-evaluates monthly (the whole point of regime detection is
        # responsiveness; its backtest entry is run_regime_adaptive_monthly_*).
        cadence=CADENCE_MONTHLY,
        # Capability ≠ funding: the mode can produce targets / (F004) trade, but
        # it ships research-state until the user funds it after paper validation.
        funding_state=FUNDING_RESEARCH,
        description="基于市场状态（正常/熊市/危机）自适应的多资产研究组合，月度调仓；研究态，前向验证中。",
    ),
    # B067 F001 — CN attack advisory modes (P2). Same daily-monitor / no-trade-band
    # engine, two factor variants (quality+momentum vs pure momentum), each its own
    # daily target / recommendation / account. Research-state and honestly caveated:
    # B066 P1 found the out-of-sample period a momentum reversal (CAGR −9~−11%), so
    # these are advisory-only, unvalidated — never an implication of a funded edge.
    StrategyMode(
        id="cn_attack_quality_momentum",
        strategy_id=CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        display_name="A股 进攻·质量动量（研究态）",
        target_producer="workbench_api.strategy_modes.cn_attack_precompute",
        # No per-mode backtest is wired off the registry: the B066 backtest is run
        # via the strategies list (cn_attack_momentum_quality), not the mode key.
        backtest_key=None,
        cadence=CADENCE_DAILY,
        funding_state=FUNDING_RESEARCH,
        description=(
            "A股 进攻型选股：质量过滤 + 12-1 动量，每日监控 / 不动区。研究态：未经样本外验证，"
            "B066 样本外为动量逆转期（样本外表现以验证卡片为准 / see verification card）；"
            "advisory-only，不自动下单，非收益预测。"
        ),
    ),
    StrategyMode(
        id="cn_attack_pure_momentum",
        strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        display_name="A股 进攻·纯动量（研究态）",
        target_producer="workbench_api.strategy_modes.cn_attack_precompute",
        backtest_key=None,
        cadence=CADENCE_DAILY,
        funding_state=FUNDING_RESEARCH,
        description=(
            "A股 进攻型选股：纯 12-1 动量（无质量过滤），每日监控 / 不动区。研究态：未验证，"
            "B066 样本外为动量逆转期（样本外表现以验证卡片为准 / see verification card）；"
            "advisory-only，不自动下单，非收益预测。"
        ),
    ),
)

_MODES_BY_ID: dict[str, StrategyMode] = {mode.id: mode for mode in _MODES}
_MODES_BY_STRATEGY: dict[str, StrategyMode] = {
    mode.strategy_id: mode for mode in _MODES
}


def list_modes() -> tuple[StrategyMode, ...]:
    """All registered modes in selector order (flagship first)."""

    return _MODES


def get_mode(mode_id: str) -> StrategyMode | None:
    """Resolve a mode by its ``id`` (``None`` if unknown)."""

    return _MODES_BY_ID.get(mode_id)


def mode_for_strategy(strategy_id: str) -> StrategyMode | None:
    """Resolve a mode by its canonical ``strategy_id`` (``None`` if unknown)."""

    return _MODES_BY_STRATEGY.get(strategy_id)


def default_mode() -> StrategyMode:
    """The default mode (Master) — the backward-compatible path when no mode is
    specified (B057 §2: an absent mode parameter means Master)."""

    return _MODES_BY_ID["master"]

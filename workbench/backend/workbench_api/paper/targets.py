"""B056 F001 — strategy target loader (parameterized by strategy_id).

The paper engine follows a strategy's *published* target allocation. This module
resolves "what is strategy X's current target?" — parameterized by ``strategy_id``.

**B057 F001 — delegates to the generic target layer.** The canonical resolver is
now ``strategy_modes.targets.get_target`` (reads ``recommendation_snapshot``
keyed by ``strategy_id``). This module keeps the paper-shaped
:class:`StrategyTargets` DTO + the paper selector list, but the actual read goes
through the single generic source so the paper engine, recommendations read path
and (B057 F004) execution chain never drift apart (framework v0.9.42 §17.1).
Because the resolver is generic, *any* mode with precomputed targets resolves
here — Master is wired today; the regime mode lights up automatically once its
precompute writes targets (B057 F003 adds it to :data:`PAPER_STRATEGIES`).

The ``target_key`` is a deterministic fingerprint of the sorted (symbol, weight)
set: identical allocation → identical key → no rebalance; a changed allocation →
new key → rebalance day. The cadence-agnostic "is today a rebalance day?" signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from workbench_api.strategy_modes.registry import MASTER_STRATEGY_ID, list_modes
from workbench_api.strategy_modes.targets import compute_target_key, get_target

__all__ = [
    "CASH_SENTINEL_SYMBOLS",
    "MASTER_STRATEGY_ID",
    "PAPER_STRATEGIES",
    "StrategyTargets",
    "compute_target_key",
    "load_strategy_targets",
    "paper_strategy_name",
]

# B074 F002 — cash-sentinel pseudo-symbols a precompute publishes to represent a
# strategy's INTENTIONALLY uninvested cash buffer (cn_attack's
# ``CN_ATTACK_CASH_SYMBOL = "CASH"``, written when the A-share book holds a cash
# buffer with no tradeable cash proxy). The published snapshot carries a real
# ``target_weight`` on this row so the allocation sums to 1.0, but it is NOT a
# security the paper engine builds: it has no price mark, so the engine would skip
# it for want of a mark and leave ``build_complete`` False forever (B074 root cause
# #2 — even after the A-share marks land, the cn_attack books never reached
# build_complete because "CASH" counted as an unbuildable skipped target). Stripping
# it here lets the engine invest only the security weights and leave the cash weight
# as residual cash (the buffer is realised naturally). ``target_key`` stays the
# FULL-target fingerprint (``get_target`` hashes every row incl. cash), so a change
# in the cash buffer still flips the key (a real rebalance). Master / regime publish
# no such pseudo-symbol (their cash proxy is a real, marked ETF — SGOV), so this is a
# no-op for them (US/Master/regime zero-regression).
CASH_SENTINEL_SYMBOLS: frozenset[str] = frozenset({"CASH"})

# Strategies surfaced in the paper engine selector, derived from the B057 mode
# registry (selector order, Master flagship first). Every mode is paper-enabled
# (the platform vision: each mode self-contained with its own forward-simulation
# account), so deriving from the registry means a future mode auto-appears in
# the paper selector with zero changes here — and the Chinese display name lives
# in one place (the registry), not duplicated. B057 F003 lights up regime.
PAPER_STRATEGIES: tuple[tuple[str, str], ...] = tuple(
    (mode.strategy_id, mode.display_name) for mode in list_modes()
)


def paper_strategy_name(strategy_id: str) -> str:
    """Chinese display name for a paper strategy (falls back to the id)."""

    for sid, name in PAPER_STRATEGIES:
        if sid == strategy_id:
            return name
    return strategy_id


@dataclass(frozen=True, slots=True)
class StrategyTargets:
    """A strategy's current target allocation + its fingerprint."""

    strategy_id: str
    weights: dict[str, float]  # SYMBOL -> target weight (upper-cased)
    target_key: str


def load_strategy_targets(
    session: Session, strategy_id: str
) -> StrategyTargets | None:
    """Resolve ``strategy_id``'s current target weights, or ``None`` if absent.

    Delegates to the generic target layer (``strategy_modes.targets.get_target``),
    which reads the latest ``recommendation_snapshot`` rows for the strategy.
    Returns the paper-shaped :class:`StrategyTargets` so the engine is unchanged.
    """

    target = get_target(session, strategy_id)
    if target is None:
        return None
    # Drop cash-sentinel pseudo-symbols (B074 F002): the paper engine builds only
    # securities — the cash weight stays as residual cash. ``target_key`` keeps the
    # FULL-target fingerprint from ``get_target`` (incl. the cash row) so a buffer
    # change still counts as a new allocation.
    weights = {
        symbol: weight
        for symbol, weight in target.weights.items()
        if symbol.upper() not in CASH_SENTINEL_SYMBOLS
    }
    return StrategyTargets(
        strategy_id=target.strategy_id,
        weights=weights,
        target_key=target.target_key,
    )

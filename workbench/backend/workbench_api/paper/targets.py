"""B056 F001 — strategy target loader (parameterized by strategy_id).

The paper engine follows a strategy's *published* target allocation. This module
resolves "what is strategy X's current target?" — parameterized by ``strategy_id``
so Master is wired today and B055 / future strategies plug in by adding a branch,
never by forking the engine.

* **Master Portfolio** reads ``recommendation_snapshot.latest_snapshot()`` — the
  same daily-precomputed target weights the Recommendations page shows. The
  weights are based on the quarterly signal date, so they are stable within a
  quarter; the engine rebalances only when the ``target_key`` fingerprint changes
  (a new quarter's allocation), never on daily price jitter.

The ``target_key`` is a deterministic fingerprint of the sorted (symbol, weight)
set: identical allocation → identical key → no rebalance; a changed allocation →
new key → rebalance day. This is the parameterized "is today a rebalance day?"
signal — it works for any cadence (Master quarterly, B055 monthly) without a
hard-coded calendar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)

MASTER_STRATEGY_ID = "master_portfolio"


@dataclass(frozen=True, slots=True)
class StrategyTargets:
    """A strategy's current target allocation + its fingerprint."""

    strategy_id: str
    weights: dict[str, float]  # SYMBOL -> target weight (upper-cased)
    target_key: str


def compute_target_key(weights: dict[str, float]) -> str:
    """Deterministic fingerprint of a target allocation.

    Weights are rounded to 6 dp and sorted by symbol so the key is stable across
    dict ordering and the per-symbol rounding the real precompute carries; a
    genuine allocation change (new quarter) flips the key."""

    items = sorted((sym.upper(), round(float(w), 6)) for sym, w in weights.items())
    raw = ";".join(f"{sym}:{w:.6f}" for sym, w in items)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_strategy_targets(
    session: Session, strategy_id: str
) -> StrategyTargets | None:
    """Resolve ``strategy_id``'s current target weights, or ``None`` if absent.

    Master reads the latest recommendation snapshot. B055 / future strategies add
    a branch here (same return shape) — the engine and the daily job are unchanged.
    """

    if strategy_id == MASTER_STRATEGY_ID:
        rows = RecommendationSnapshotRepository(session).latest_snapshot()
        if not rows:
            return None
        weights = {row.symbol.upper(): float(row.target_weight) for row in rows}
        return StrategyTargets(
            strategy_id=strategy_id,
            weights=weights,
            target_key=compute_target_key(weights),
        )
    return None

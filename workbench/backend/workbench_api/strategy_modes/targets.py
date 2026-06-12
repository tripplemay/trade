"""B057 F001 — the generic strategy target layer.

``get_target(session, strategy_id)`` answers "what is strategy X's current
target allocation?" for **any** mode, reading the shared
``recommendation_snapshot`` table now keyed by ``strategy_id`` (B057 migration
0020). Master and regime read from the *same* source through the *same*
function — that single-source unification is the heart of F001 and avoids the
"same entity, two readers that drift apart" anti-pattern (framework v0.9.42
§17.1).

This module is on the **request path** side of the §12.10 boundary: it only
reads the precomputed snapshot from the DB and never imports ``trade`` (the
scoring lives in the precompute jobs). ``paper/targets.py`` delegates here so
the paper engine, the recommendations read path and (B057 F004) the execution
chain all resolve targets through one function.

The ``target_key`` is a deterministic fingerprint of the sorted (symbol,
weight) set — identical allocation → identical key → no rebalance; a changed
allocation (a new period) → new key → rebalance day. It is the cadence-agnostic
"is today a rebalance day?" signal reused by the paper engine and (F004) the
execution chain.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.strategy_modes.registry import MASTER_STRATEGY_ID


@dataclass(frozen=True, slots=True)
class StrategyTarget:
    """A mode's current target allocation + provenance.

    ``weights`` keys are upper-cased symbols → target weight (summing to ~1.0).
    ``as_of_date`` is the signal date the target is "as of" (stable within a
    period). ``meta`` is the run-level metadata the producer denormalised onto
    the snapshot (data_source, signal_date, regime label, …).
    """

    strategy_id: str
    weights: dict[str, float]
    as_of_date: date | None
    target_key: str
    meta: dict[str, Any] = field(default_factory=dict)


def compute_target_key(weights: dict[str, float]) -> str:
    """Deterministic fingerprint of a target allocation.

    Weights are rounded to 6 dp and sorted by symbol so the key is stable across
    dict ordering and the per-symbol rounding the real precompute carries; a
    genuine allocation change (new period) flips the key. This is the canonical
    home — ``paper/targets.py`` re-exports it so every target source uses the
    same fingerprint (framework v0.9.41 §17 single-source).
    """

    items = sorted((sym.upper(), round(float(w), 6)) for sym, w in weights.items())
    raw = ";".join(f"{sym}:{w:.6f}" for sym, w in items)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def get_target(
    session: Session, strategy_id: str = MASTER_STRATEGY_ID
) -> StrategyTarget | None:
    """Resolve ``strategy_id``'s current target, or ``None`` if none exists.

    Reads the latest ``recommendation_snapshot`` rows for the strategy (the
    producer writes them; this never imports ``trade``). Defaults to Master so a
    caller that omits the strategy gets the backward-compatible flagship target
    (B057 §2). The returned ``weights`` are upper-cased symbol → weight.
    """

    rows = RecommendationSnapshotRepository(session).latest_snapshot(
        strategy_id=strategy_id
    )
    if not rows:
        return None
    weights = {row.symbol.upper(): float(row.target_weight) for row in rows}
    return StrategyTarget(
        strategy_id=strategy_id,
        weights=weights,
        as_of_date=rows[0].as_of_date,
        target_key=compute_target_key(weights),
        meta=dict(rows[0].master_meta or {}),
    )

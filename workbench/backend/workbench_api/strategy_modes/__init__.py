"""B057 F001 — generalized "strategy mode" platform layer.

Before B057 the workbench had one first-class strategy: the Master Portfolio.
Its target allocation, paper account, backtest and surfaces were all
Master-only. B057 promotes "strategy mode" to a parameterised first-class
citizen so any strategy (Master, regime-adaptive, future B055 …) plugs in at
minimal cost and can — eventually — trade independently.

This package owns the cross-cutting platform pieces:

* :mod:`registry` — the canonical mode registry (id / display_name /
  strategy_id / target_producer / backtest_key / cadence / funding_state).
  The single source of truth the recommendations, paper, backtest, execution
  and frontend surfaces read to enumerate the available modes.
* :mod:`targets` — the **generic target layer**: ``get_target(session,
  strategy_id)`` reads each mode's current target allocation from the shared
  ``recommendation_snapshot`` table (now keyed by ``strategy_id``). Master and
  regime read from the *same* source — that is the F001 unification.
* :mod:`regime_precompute` / :mod:`cli` — the regime-adaptive target producer
  (imports ``trade`` inside the job, §12.10.2) that writes the regime mode's
  current target into the generic target layer on a monthly cadence.

Honesty boundary (B057 §1): building a mode's target/account/execution chain
gives the *capability* to trade it; **funding stays the user's decision**.
A mode's :attr:`registry.StrategyMode.funding_state` marks whether it is live
(Master) or research / forward-validation only (regime) so the surfaces never
imply a research-state mode is funded.
"""

from __future__ import annotations

from workbench_api.strategy_modes.registry import (
    MASTER_STRATEGY_ID,
    REGIME_STRATEGY_ID,
    StrategyMode,
    default_mode,
    get_mode,
    list_modes,
    mode_for_strategy,
)
from workbench_api.strategy_modes.targets import (
    StrategyTarget,
    compute_target_key,
    get_target,
)

__all__ = [
    "MASTER_STRATEGY_ID",
    "REGIME_STRATEGY_ID",
    "StrategyMode",
    "StrategyTarget",
    "compute_target_key",
    "default_mode",
    "get_mode",
    "get_target",
    "list_modes",
    "mode_for_strategy",
]

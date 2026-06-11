"""B056 — paper-trading (forward-simulation) engine.

A parameterized virtual-account engine: give a strategy virtual capital, follow
its published target allocation, rebalance at the strategy's rebalance points
(close-price fills + real costs), and mark to market daily. Master Portfolio is
the first strategy wired; B055 / future strategies plug into the SAME engine via
the same target interface (``targets.load_strategy_targets``).

The engine (``engine.compute_rebalance``) is **pure** — it takes cash +
positions + target weights + price marks and returns the new book, never
touching the ORM or the network. ``service`` wires it to the repositories;
``cli`` is the off-request-path activation entrypoint. The forward MTM loop and
its timer live in F002.
"""

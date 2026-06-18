"""B050 F001 — per-strategy result adapters.

Each ``trade`` engine returns a differently-shaped result object; these pure
adapters map each to the ``BacktestRunResponse`` field dicts
(``equity`` / ``allocations`` / ``trades``). Per-strategy adapters (not one
giant branching mapper) keep each engine's field-name quirks isolated and unit
-testable.

- master → ``mapping.py`` (``map_*``, unchanged; ``portfolio_target_weights`` +
  per-period ``starting_value``).
- momentum / risk_parity → here.
- us_quality (F002) + hk_china (F003) add their own adapters.

Pure — the result objects are passed in by the worker, so no ``trade`` import at
module load (same posture as ``mapping.py``).
"""

from __future__ import annotations

from typing import Any

from workbench_api.backtests.mapping import map_equity


def _fill_to_trade(fill: Any, base_value: float) -> dict[str, Any] | None:
    """One ``BacktestTrade`` row from a rebalance fill, or ``None`` when the fill
    has no executable price (missing T+1 open).

    The fills carry a ``target_weight`` + execution price (a rebalance to target),
    not a signed quantity — so notional = ``target_weight × base_value`` and
    quantity = notional / execution_price, surfaced as the executed buy leg (same
    convention as the master ``map_trades``)."""

    price = float(fill.execution_price)
    if price <= 0:
        return None
    notional = float(fill.target_weight) * base_value
    return {
        "date": fill.execution_date.isoformat(),
        "symbol": fill.symbol,
        "side": "buy",
        "quantity": round(notional / price, 6),
        "price": price,
        "notional": round(notional, 2),
    }


def _iso_date(value: Any) -> str:
    """ISO ``YYYY-MM-DD`` from a date / pandas Timestamp / string."""

    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    return str(value)[:10]


def _allocation_row(signal: Any) -> dict[str, Any]:
    """``AllocationBar`` row from a strategy signal (``signal_date`` +
    ``target_weights``) — the per-signal-date target the sleeve rebalanced to."""

    return {
        "date": signal.signal_date.isoformat(),
        "weights": {symbol: float(weight) for symbol, weight in signal.target_weights.items()},
    }


def adapt_momentum(result: Any) -> dict[str, list[dict[str, Any]]]:
    """Adapt ``MonthlyBacktestResult`` (momentum) → equity/allocations/trades.

    Multi-month runs expose each month as a nested ``MonthlyBacktestResult`` in
    ``rebalance_results`` (each carries its own ``signal`` + ``fills`` +
    ``starting_capital``); a single-month run is its own only rebalance."""

    rebalances = result.rebalance_results or (result,)
    allocations = [_allocation_row(sub.signal) for sub in rebalances]
    trades: list[dict[str, Any]] = []
    for sub in rebalances:
        base = float(sub.starting_capital)
        for fill in sub.fills:
            row = _fill_to_trade(fill, base)
            if row is not None:
                trades.append(row)
    return {"equity": map_equity(result), "allocations": allocations, "trades": trades}


def adapt_risk_parity(result: Any) -> dict[str, list[dict[str, Any]]]:
    """Adapt ``RiskParityBacktestResult`` → equity/allocations/trades.

    Each ``RiskParityPeriodResult`` carries the rebalance ``signal`` (with
    ``signal_date`` + ``target_weights``) and ``fills``. The period exposes
    ``ending_value`` (post-rebalance) — not ``starting_value`` — so that is the
    notional base for the executed legs."""

    allocations = [_allocation_row(period.signal) for period in result.rebalance_results]
    trades: list[dict[str, Any]] = []
    for period in result.rebalance_results:
        base = float(period.ending_value)
        for fill in period.fills:
            row = _fill_to_trade(fill, base)
            if row is not None:
                trades.append(row)
    return {"equity": map_equity(result), "allocations": allocations, "trades": trades}


def adapt_regime(result: Any) -> dict[str, list[dict[str, Any]]]:
    """Adapt ``RegimeAdaptiveBacktestResult`` (B057) → equity/allocations/trades.

    Each ``RegimeAdaptivePeriodResult`` carries ``signal_date`` +
    ``effective_weights`` (the post-tolerance allocation actually held) +
    ``fills`` directly (not nested under a ``signal`` like risk_parity). The
    period exposes ``ending_value`` (post-rebalance) — the notional base for the
    executed legs. Zero-weight universe entries are dropped from the surfaced
    allocation (regime spans the full 9-asset universe with most at 0.0)."""

    allocations = [
        {
            "date": period.signal_date.isoformat(),
            "weights": {
                symbol: float(weight)
                for symbol, weight in period.effective_weights.items()
                if float(weight) > 0
            },
        }
        for period in result.rebalance_results
    ]
    trades: list[dict[str, Any]] = []
    for period in result.rebalance_results:
        base = float(period.ending_value)
        for fill in period.fills:
            row = _fill_to_trade(fill, base)
            if row is not None:
                trades.append(row)
    return {"equity": map_equity(result), "allocations": allocations, "trades": trades}


def adapt_us_quality(result: Any) -> dict[str, list[dict[str, Any]]]:
    """Adapt ``UsQualityBacktestResult`` → equity/allocations/trades.

    The equity curve is a daily ``pd.DataFrame`` (columns ``date`` / ``equity``),
    converted to ``EquitySample`` rows here (the shared ``map_equity`` only
    handles ``tuple[EquityPoint]``). Allocations come from ``rebalance_periods``
    (``signal_date`` + ``target_weights``). The engine reports no per-leg fills,
    so trades is intentionally **empty** — we surface the honest absence rather
    than fabricate execution legs. Accesses the DataFrame/columns via their own
    methods, so no pandas import is needed here."""

    curve = result.equity_curve
    equity = [
        {"date": _iso_date(d), "nav": float(v)}
        for d, v in zip(
            curve["date"].tolist(), curve["equity"].tolist(), strict=False
        )
    ]
    allocations = [
        {
            "date": _iso_date(period.signal_date),
            "weights": {symbol: float(weight) for symbol, weight in period.target_weights.items()},
        }
        for period in result.rebalance_periods
    ]
    return {"equity": equity, "allocations": allocations, "trades": []}


def adapt_cn_attack(result: Any) -> dict[str, list[dict[str, Any]]]:
    """Adapt the headline ``CnAttackBacktestResult`` (B066 F003) → equity/allocations/trades.

    Like ``adapt_us_quality``, the equity curve is a daily ``pd.DataFrame`` and the
    engine reports no per-leg fills (it records daily turnover, not priced legs), so
    trades is intentionally **empty** (no fabricated legs). Allocations are surfaced
    on rebalance days from the daily records as the equal-weight target among that
    day's names — the engine builds an equal-weighted top-N portfolio, so 1/N is the
    held weight (the position cap rarely binds at top 20-30). The chart shows this
    headline variant; the full 6-variant comparison lives in ``report_markdown``."""

    curve = result.equity_curve
    equity = [
        {"date": _iso_date(d), "nav": float(v)}
        for d, v in zip(curve["date"].tolist(), curve["equity"].tolist(), strict=False)
    ]
    allocations: list[dict[str, Any]] = []
    for record in result.daily_records:
        if record.rebalanced and record.target_tickers:
            weight = 1.0 / len(record.target_tickers)
            allocations.append(
                {
                    "date": _iso_date(record.date),
                    "weights": {ticker: weight for ticker in record.target_tickers},
                }
            )
    return {"equity": equity, "allocations": allocations, "trades": []}

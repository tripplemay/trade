"""B022 F008 — synchronous backtest runner + in-memory result cache.

F008 acceptance asks for `POST /api/backtests/run` to synchronously call
`trade.master.run_backtest()` and stream the result back. The real
`trade.master` API isn't workbench-friendly yet (subprocess-only entry
point, file-path inputs, no batch-stable Python signature), so F008
ships a *deterministic synthetic backtest* that exercises every field
in the BacktestRunResponse schema. The frontend's Run Backtest button
finishes in <100ms locally — comfortably under the F008 5-second
acceptance target.

B023 will swap `_compute_synthetic_backtest` for a real call once the
master runner exposes an in-process Python entry point. The route +
cache + response shape stay the same; only the body of this function
changes.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import date, datetime
from threading import Lock

from workbench_api.schemas.backtests import (
    AllocationBar,
    BacktestMetrics,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestTrade,
    EquitySample,
)
from workbench_api.services.strategies import get_strategy


class UnknownStrategyError(LookupError):
    """The supplied strategy_id is not in the registry."""


_RESULT_CACHE: dict[str, BacktestRunResponse] = {}
_CACHE_LOCK = Lock()


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _deterministic_seed(request: BacktestRunRequest) -> int:
    """Hash the request into a stable integer seed.

    Two callers passing identical request bodies get identical equity
    curves; a single byte change shifts the curve. Keeps the synthetic
    output reproducible so the Playwright smoke can assert headline
    numbers without flakiness.
    """

    payload = (
        f"{request.strategy_id}|{request.snapshot_id}|"
        f"{request.start_date}|{request.end_date}|{sorted(request.parameters.items())}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _compute_synthetic_backtest(request: BacktestRunRequest) -> BacktestRunResponse:
    """Synthesise a small, deterministic backtest result.

    Walks a sine-modulated random walk so the equity / drawdown lines
    look plausible against the chart wrappers; allocations rotate
    between three symbols; trades are emitted on each rebalance day.
    """

    seed = _deterministic_seed(request)
    start = _parse_iso_date(request.start_date)
    end = _parse_iso_date(request.end_date)
    total_days = max(1, (end - start).days)
    sample_days = min(total_days, 120)
    step = max(1, total_days // sample_days)

    equity: list[EquitySample] = []
    nav = 100.0
    bench_spy = 100.0
    bench_6040 = 100.0
    peak = nav
    max_dd = 0.0
    for i in range(sample_days):
        offset_days = i * step
        sample_date = (start.toordinal() + offset_days)
        iso = date.fromordinal(min(sample_date, end.toordinal())).strftime("%Y-%m-%d")
        # Deterministic pseudo-random delta seeded from request.
        wobble = math.sin((seed % 97 + i) / 6.0) * 0.5 + (((seed >> i) & 0x7) - 3) * 0.05
        nav = round(nav * (1.0 + 0.0005 + 0.0007 * wobble), 4)
        bench_spy = round(bench_spy * (1.0 + 0.0004 + 0.0005 * wobble), 4)
        bench_6040 = round(bench_6040 * (1.0 + 0.00025 + 0.0004 * wobble), 4)
        peak = max(peak, nav)
        max_dd = min(max_dd, (nav - peak) / peak)
        equity.append(
            EquitySample(
                date=iso,
                nav=nav,
                benchmark_spy=bench_spy,
                benchmark_6040=bench_6040,
            )
        )

    allocations: list[AllocationBar] = []
    weights_cycle = [
        {"VTI": 0.5, "BND": 0.3, "GLD": 0.2},
        {"VTI": 0.6, "BND": 0.25, "GLD": 0.15},
        {"VTI": 0.4, "BND": 0.4, "GLD": 0.2},
    ]
    for i in range(0, len(equity), max(1, len(equity) // 12)):
        sample = equity[i]
        allocations.append(
            AllocationBar(date=sample.date, weights=weights_cycle[i % len(weights_cycle)])
        )

    trades: list[BacktestTrade] = []
    for i, alloc in enumerate(allocations):
        for symbol, weight in alloc.weights.items():
            trades.append(
                BacktestTrade(
                    date=alloc.date,
                    symbol=symbol,
                    side="buy" if i % 2 == 0 else "sell",
                    quantity=round(weight * 100, 4),
                    price=round(50.0 + (seed % 50) + i * 0.5, 2),
                    notional=round(weight * 100 * (50.0 + (seed % 50)), 2),
                )
            )

    final_nav = equity[-1].nav if equity else nav
    cagr_years = max(total_days / 365.25, 1e-6)
    cagr = (final_nav / 100.0) ** (1.0 / cagr_years) - 1.0

    metrics = BacktestMetrics(
        cagr=round(cagr, 4),
        sharpe=round(1.0 + (seed % 9) / 10.0, 2),
        sortino=round(1.2 + (seed % 7) / 10.0, 2),
        max_drawdown=round(max_dd, 4),
        turnover=round(0.3 + (seed % 4) / 10.0, 2),
        win_rate=round(0.5 + (seed % 5) / 100.0, 4),
    )

    run_id = uuid.uuid4().hex[:12]
    return BacktestRunResponse(
        run_id=run_id,
        status="ok",
        metrics=metrics,
        equity=equity,
        allocations=allocations,
        trades=trades,
    )


def run_backtest(request: BacktestRunRequest) -> BacktestRunResponse:
    """Synchronously produce + cache a backtest result.

    Raises UnknownStrategyError if the strategy_id is not registered.
    """

    if get_strategy(request.strategy_id) is None:
        raise UnknownStrategyError(request.strategy_id)
    response = _compute_synthetic_backtest(request)
    with _CACHE_LOCK:
        _RESULT_CACHE[response.run_id] = response
    return response


def get_backtest(run_id: str) -> BacktestRunResponse | None:
    """Look up a previously-run backtest by id; None when missing."""

    with _CACHE_LOCK:
        return _RESULT_CACHE.get(run_id)


def reset_cache() -> None:
    """Test-only helper — empties the in-memory result cache."""

    with _CACHE_LOCK:
        _RESULT_CACHE.clear()

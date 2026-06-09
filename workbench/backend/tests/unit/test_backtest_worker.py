"""B047 F002 — backtest worker queue processing + result mapping.

The real-engine run (run_backtest_job → run_master_portfolio_quarterly_backtest)
needs the VM's daily unified data, so it is exercised by F005 L2 on the VM.
Here we test the worker's QUEUE/SAVE logic with a monkeypatched job, and the
pure result→schema mapping with a fake engine result.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from workbench_api.backtests import worker as worker_mod
from workbench_api.backtests.mapping import (
    map_allocations,
    map_equity,
    map_metrics,
    map_trades,
)
from workbench_api.db.engine import get_engine
from workbench_api.db.models.backtest_run import STATUS_DONE, STATUS_ERROR
from workbench_api.db.repositories.backtest_run import BacktestRunRepository

_MAPPED = {
    "metrics": {"cagr": 0.1, "sharpe": 1.0, "sortino": None, "max_drawdown": -0.2,
                "turnover": 2.0, "win_rate": None},
    "equity": [{"date": "2024-01-01", "nav": 100.0}],
    "allocations": [{"date": "2024-01-01", "weights": {"SPY": 1.0}}],
    "trades": [{"date": "2024-01-02", "symbol": "SPY", "side": "buy",
                "quantity": 1.0, "price": 100.0, "notional": 100.0}],
    "report_markdown": "# Backtest report",
}


# --- result → schema mapping (pure) ---------------------------------------


def _fake_result() -> SimpleNamespace:
    fill = SimpleNamespace(
        symbol="SPY", target_weight=0.5, execution_date=date(2024, 1, 2),
        execution_price=100.0,
    )
    bad_fill = SimpleNamespace(  # missing T+1 open → skipped
        symbol="VEA", target_weight=0.5, execution_date=date(2024, 1, 2),
        execution_price=0.0,
    )
    period = SimpleNamespace(
        signal_date=date(2024, 1, 1),
        starting_value=10_000.0,
        portfolio_target_weights={"SPY": 0.5, "VEA": 0.5},
        fills=(fill, bad_fill),
    )
    return SimpleNamespace(
        equity_curve=(
            SimpleNamespace(date=date(2024, 1, 1), value=10_000.0),
            SimpleNamespace(date=date(2024, 3, 31), value=10_500.0),
        ),
        rebalance_results=(period,),
    )


def test_map_metrics_reads_report_payload() -> None:
    payload = {"metrics": {"CAGR": 0.12, "Sharpe": 1.3, "max_drawdown": -0.15, "turnover": 3.0}}
    m = map_metrics(payload)
    assert m["cagr"] == 0.12 and m["sharpe"] == 1.3
    assert m["max_drawdown"] == -0.15 and m["turnover"] == 3.0
    assert m["sortino"] is None and m["win_rate"] is None


def test_map_equity_allocations_trades() -> None:
    result = _fake_result()
    eq = map_equity(result)
    assert eq == [
        {"date": "2024-01-01", "nav": 10_000.0},
        {"date": "2024-03-31", "nav": 10_500.0},
    ]
    alloc = map_allocations(result)
    assert alloc[0]["date"] == "2024-01-01"
    assert alloc[0]["weights"] == {"SPY": 0.5, "VEA": 0.5}
    trades = map_trades(result)
    # Only the priced fill survives (VEA's 0.0 execution price is skipped).
    assert len(trades) == 1
    assert trades[0]["symbol"] == "SPY"
    assert trades[0]["notional"] == pytest.approx(5_000.0)  # 0.5 × 10_000
    assert trades[0]["quantity"] == pytest.approx(50.0)  # 5000 / 100


# --- queue processing (monkeypatched engine) ------------------------------


def test_process_next_saves_done_result(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(get_engine()) as setup:
        run = BacktestRunRepository(setup).enqueue(strategy_id="momentum", params={})
        setup.commit()
        run_id = run.run_id

    monkeypatch.setattr(worker_mod, "run_backtest_job", lambda _run, _explainer=None: _MAPPED)
    with Session(get_engine()) as session:
        handled = worker_mod.process_next(session)
        assert handled is True
        row = BacktestRunRepository(session).get_by_run_id(run_id)
        assert row is not None
        assert row.status == STATUS_DONE
        assert row.metrics is not None
        assert row.metrics["sharpe"] == 1.0
        assert row.report_markdown == "# Backtest report"
        assert row.finished_at is not None


def test_process_next_saves_error_on_engine_failure(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(get_engine()) as setup:
        run = BacktestRunRepository(setup).enqueue(strategy_id="momentum", params={})
        setup.commit()
        run_id = run.run_id

    def _boom(_run: object, _explainer: object = None) -> dict[str, object]:
        raise worker_mod.BacktestWorkerError("no data")

    monkeypatch.setattr(worker_mod, "run_backtest_job", _boom)
    with Session(get_engine()) as session:
        handled = worker_mod.process_next(session)
        assert handled is True
        row = BacktestRunRepository(session).get_by_run_id(run_id)
        assert row is not None
        assert row.status == STATUS_ERROR
        assert "no data" in (row.error or "")
        assert row.finished_at is not None


def test_process_next_records_structured_error_kind(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B047-OPS2 F001 — a classified engine failure stores error_kind so the
    frontend maps a friendly bilingual message (not the raw exception)."""

    with Session(get_engine()) as setup:
        run = BacktestRunRepository(setup).enqueue(strategy_id="momentum", params={})
        setup.commit()
        run_id = run.run_id

    def _insufficient(_run: object, _explainer: object = None) -> dict[str, object]:
        raise worker_mod.BacktestWorkerError(
            "insufficient price history for any signal date in range: no valid "
            "volatility estimates for risk assets"
        )

    monkeypatch.setattr(worker_mod, "run_backtest_job", _insufficient)
    with Session(get_engine()) as session:
        assert worker_mod.process_next(session) is True
        row = BacktestRunRepository(session).get_by_run_id(run_id)
        assert row is not None
        assert row.status == STATUS_ERROR
        assert row.error_kind == "insufficient_history"


def test_process_next_empty_queue_returns_false(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        assert worker_mod.process_next(session) is False


def test_main_runs_bounded_iterations(initialised_db: str) -> None:
    # Empty queue → each iteration sleeps poll_seconds; 0.0 keeps the bounded
    # loop instant without patching time.sleep.
    assert worker_mod.main(poll_seconds=0.0, max_iterations=2) == 0

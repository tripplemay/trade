"""B047 F004 — investment_report repo + canonical report generation."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from workbench_api.backtests import canonical
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.investment_report import InvestmentReportRepository

_MAPPED = {
    "metrics": {"cagr": 0.1, "sharpe": 1.0, "sortino": None, "max_drawdown": -0.2,
                "turnover": 2.0, "win_rate": None},
    "equity": [{"date": "2026-03-31", "nav": 110.0}],
    "allocations": [],
    "trades": [],
    "report_markdown": "# Master Portfolio Report\n\n- CAGR: 0.10",
}


def test_upsert_inserts_then_replaces(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = InvestmentReportRepository(session)
        repo.upsert_report(
            strategy_id="master_portfolio", as_of_date=date(2026, 3, 31),
            title="v1", markdown="# v1", metrics={"cagr": 0.1},
            computed_at=datetime(2026, 6, 8, tzinfo=UTC),
        )
        session.commit()
        # Same (strategy, date) → replace, not duplicate.
        repo.upsert_report(
            strategy_id="master_portfolio", as_of_date=date(2026, 3, 31),
            title="v2", markdown="# v2", metrics={"cagr": 0.2},
            computed_at=datetime(2026, 6, 8, tzinfo=UTC),
        )
        session.commit()
        rows = repo.list_reports()
        assert len(rows) == 1
        assert rows[0].title == "v2"
        assert rows[0].slug == "master_portfolio-2026-03-31"
        assert repo.get_by_slug("master_portfolio-2026-03-31") is not None
        assert repo.get_by_slug("nope") is None


def test_generate_canonical_reports_writes_investment_report(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(canonical, "run_backtest_job", lambda _run: _MAPPED)
    with Session(get_engine()) as session:
        count = canonical.generate_canonical_reports(session, as_of=date(2026, 3, 31))
        assert count == 1
        rows = InvestmentReportRepository(session).list_reports()
        assert len(rows) == 1
        assert rows[0].strategy_id == "master_portfolio"
        assert rows[0].kind == "investment"
        assert rows[0].markdown.startswith("# Master Portfolio Report")
        assert rows[0].metrics_json is not None
        assert rows[0].metrics_json["sharpe"] == 1.0


def test_generate_canonical_reports_propagates_engine_error(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_run: object) -> dict[str, object]:
        raise RuntimeError("no data")

    monkeypatch.setattr(canonical, "run_backtest_job", _boom)
    with Session(get_engine()) as session, pytest.raises(RuntimeError, match="no data"):
        canonical.generate_canonical_reports(session, as_of=date(2026, 3, 31))

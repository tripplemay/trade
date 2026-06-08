"""B040 F001 — ReportDetail.metrics structured parse.

Covers the header-signature recognition, synonym mapping
(annualized_return→cagr / annualized_volatility→volatility / mdd→max_drawdown),
Calmar derivation (CAGR/|MDD|), graceful null (no metrics table → None, never
raises), multi-table selection, value tolerance, and body_markdown byte
integrity (the parse never mutates the original markdown).

Tables are built in-test (B016/B015-style wide shape) so the suite stays
self-contained and deterministic — it asserts parse/derive logic, never a
strategy-performance conclusion (v0.9.21 fixture-vs-real-signal policy).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from workbench_api.app import create_app
from workbench_api.schemas.reports import ReportTable
from workbench_api.services.reports import _parse_metrics
from workbench_api.settings import Settings, get_settings

SECRET = "test-secret-do-not-use-in-prod"
ALLOWED_EMAIL = "owner@example.com"


def _table(columns: list[str], rows: list[list[str]]) -> ReportTable:
    return ReportTable(caption=None, columns=columns, rows=rows)


# A B016/B015-style wide metrics table (real corpus shape).
_WIDE_COLUMNS = [
    "method",
    "annualized_return",
    "annualized_volatility",
    "sharpe",
    "max_drawdown",
    "turnover",
    "ending_value",
]
_WIDE_ROW = ["risk_parity", "0.1966", "0.3695", "0.6268", "-0.1966", "1.09", "158978.38"]


# --- _parse_metrics pure-function unit tests ------------------------------


def test_wide_table_parse_with_synonyms() -> None:
    metrics = _parse_metrics([_table(_WIDE_COLUMNS, [_WIDE_ROW])])
    assert metrics is not None
    assert metrics.cagr == pytest.approx(0.1966)  # annualized_return → cagr
    assert metrics.volatility == pytest.approx(0.3695)  # annualized_volatility → volatility
    assert metrics.sharpe == pytest.approx(0.6268)
    assert metrics.max_drawdown == pytest.approx(-0.1966)
    assert metrics.turnover == pytest.approx(1.09)
    assert metrics.sortino is None  # column absent


def test_mdd_synonym_maps_to_max_drawdown() -> None:
    metrics = _parse_metrics(
        [_table(["sharpe", "mdd"], [["1.5", "-0.08"]])]
    )
    assert metrics is not None
    assert metrics.max_drawdown == pytest.approx(-0.08)


def test_calmar_is_derived_from_cagr_and_mdd() -> None:
    metrics = _parse_metrics(
        [_table(["sharpe", "cagr", "max_drawdown"], [["1.0", "0.20", "-0.10"]])]
    )
    assert metrics is not None
    assert metrics.calmar == pytest.approx(0.20 / 0.10)  # 2.0


def test_calmar_none_when_max_drawdown_zero() -> None:
    metrics = _parse_metrics(
        [_table(["sharpe", "cagr", "max_drawdown"], [["1.0", "0.20", "0"]])]
    )
    assert metrics is not None
    assert metrics.calmar is None


def test_explicit_calmar_column_wins_over_derivation() -> None:
    metrics = _parse_metrics(
        [_table(["sharpe", "cagr", "max_drawdown", "calmar"], [["1.0", "0.20", "-0.10", "9.9"]])]
    )
    assert metrics is not None
    assert metrics.calmar == pytest.approx(9.9)  # not the derived 2.0


def test_table_without_core_metric_is_not_recognised() -> None:
    # Only ``turnover`` (no sharpe/cagr/mdd/...) — not a metrics table.
    assert _parse_metrics([_table(["window", "turnover", "status"], [["w1", "1.2", "ok"]])]) is None


def test_no_tables_returns_none() -> None:
    assert _parse_metrics([]) is None


def test_first_recognised_table_is_selected_among_many() -> None:
    non_metric = _table(["window", "status", "ending_value"], [["w1", "ok", "100"]])
    metric = _table(["sharpe", "cagr", "max_drawdown"], [["2.5", "0.30", "-0.10"]])
    metrics = _parse_metrics([non_metric, metric])
    assert metrics is not None
    assert metrics.sharpe == pytest.approx(2.5)


def test_value_tolerance_percent_and_placeholder() -> None:
    metrics = _parse_metrics(
        [_table(["sharpe", "cagr", "max_drawdown"], [["N/A", "19.66%", "-10%"]])]
    )
    assert metrics is not None
    assert metrics.sharpe is None  # "N/A" → None, not a raise
    assert metrics.cagr == pytest.approx(0.1966)  # "19.66%" → 0.1966
    assert metrics.max_drawdown == pytest.approx(-0.10)


def test_first_data_row_is_used() -> None:
    metrics = _parse_metrics(
        [_table(["sharpe", "max_drawdown"], [["1.1", "-0.05"], ["9.9", "-0.99"]])]
    )
    assert metrics is not None
    assert metrics.sharpe == pytest.approx(1.1)  # first row, not the second


# B047 F004: the get_report integration + /api/reports route metrics tests
# moved to test_reports.py (the route is now DB-backed — investment reports,
# not the filesystem). The pure `_parse_metrics` table-parser unit tests above
# stay (the parser is retained as a helper).


def test_route_detail_requires_auth(initialised_db: str) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET, ALLOWED_USER_EMAIL=ALLOWED_EMAIL
    )
    client = TestClient(app)
    assert client.get("/api/reports/B016-risk-parity-2026-05-14").status_code == 401

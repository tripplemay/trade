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

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.app import create_app
from workbench_api.auth.jwt_validator import JWT_ALGORITHM
from workbench_api.schemas.reports import ReportTable
from workbench_api.services.reports import _parse_metrics, get_report
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


# --- get_report integration + route ---------------------------------------

_REPORT_MD = """# B016 Risk Parity vs HRP

Some narrative text above the table.

| method | annualized_return | sharpe | max_drawdown | turnover |
|---|---|---|---|---|
| risk_parity | 0.1966 | 0.6268 | -0.1966 | 1.09 |
| hrp | 0.1500 | 0.5000 | -0.2500 | 0.90 |

Conclusion paragraph below.
"""

_NO_METRICS_MD = "# B099 Note\n\nJust prose, no metrics table.\n"


def _authed_client(reports_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(reports_dir),
    )
    client = TestClient(app)
    now = int(time.time())
    token = jwt.encode(
        {"email": ALLOWED_EMAIL, "sub": "rpt", "iat": now, "exp": now + 3600},
        SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("authjs.session-token", token)
    return client


def test_get_report_parses_metrics_and_keeps_body_byte_identical(tmp_path: Path) -> None:
    md_path = tmp_path / "B016-risk-parity-2026-05-14.md"
    md_path.write_text(_REPORT_MD, encoding="utf-8")
    detail = get_report("B016-risk-parity", tmp_path)
    assert detail.metrics is not None
    assert detail.metrics.sharpe == pytest.approx(0.6268)
    assert detail.metrics.calmar == pytest.approx(0.1966 / 0.1966)  # derived
    # body_markdown must be the original source, byte-for-byte.
    assert detail.body_markdown == _REPORT_MD


def test_route_returns_metrics_field_when_present(
    initialised_db: str, tmp_path: Path  # noqa: ARG001
) -> None:
    (tmp_path / "B016-risk-parity-2026-05-14.md").write_text(_REPORT_MD, encoding="utf-8")
    client = _authed_client(tmp_path)
    payload = client.get("/api/reports/B016-risk-parity").json()
    assert payload["metrics"] is not None
    assert payload["metrics"]["sharpe"] == pytest.approx(0.6268)


def test_route_metrics_is_null_without_metrics_table(
    initialised_db: str, tmp_path: Path  # noqa: ARG001
) -> None:
    (tmp_path / "B099-note-2026-05-14.md").write_text(_NO_METRICS_MD, encoding="utf-8")
    client = _authed_client(tmp_path)
    payload = client.get("/api/reports/B099-note").json()
    assert payload["metrics"] is None


def test_route_detail_requires_auth(initialised_db: str, tmp_path: Path) -> None:  # noqa: ARG001
    (tmp_path / "B016-risk-parity-2026-05-14.md").write_text(_REPORT_MD, encoding="utf-8")
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        NEXTAUTH_SECRET=SECRET,
        ALLOWED_USER_EMAIL=ALLOWED_EMAIL,
        WORKBENCH_REPORTS_DIR=str(tmp_path),
    )
    client = TestClient(app)
    assert client.get("/api/reports/B016-risk-parity").status_code == 401

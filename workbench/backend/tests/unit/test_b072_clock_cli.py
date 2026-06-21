"""B072 F003 — timer CLIs thread ``--as-of`` into their run-date seam, and omit
it → wall clock (production zero-regression).

These pin the *breadth* side of the acceptance ("全支持 --as-of 贯穿现有 seam,
默认 now 零回归"): for each timer CLI, ``--as-of D`` reaches the service as the
run date, and no flag leaves the service on its ``datetime.now(UTC)`` default.
The *depth* (golden fast-forward output) lives in
``tests/acceptance/test_b072_clock_injection.py``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from workbench_api.advisor import cli as advisor_cli
from workbench_api.backtests import canonical
from workbench_api.data_refresh import cli as data_refresh_cli
from workbench_api.news import cli as news_cli
from workbench_api.paper import mtm as paper_mtm
from workbench_api.prices import cli as prices_cli
from workbench_api.recommendations import cli as rec_cli
from workbench_api.strategy_modes import cli as regime_cli

_INJECTED = date(2022, 3, 31)
_INJECTED_MIDNIGHT = datetime(2022, 3, 31, tzinfo=UTC)


# ── recommendations precompute (deep seam: as_of → price cutoff + stamp) ──────
def _precompute_cli_fakes(summary: Any) -> tuple[dict[str, Any], Any, Any]:
    """Build (captured, fake score_fn, fake run_precompute) for a precompute CLI.

    ``fake_run`` fires the (possibly as_of-bound) ``score_fn`` so the test
    captures the date the CLI injected into the scorer, plus the ``computed_at``
    stamp the CLI derived from ``--as-of``."""

    captured: dict[str, Any] = {}

    def fake_score(*, fixture_dir: Any = None, as_of: date | None = None) -> Any:
        captured["score_as_of"] = as_of
        return None

    def fake_run(session: Any, *, score_fn: Any, computed_at: Any, **_: Any) -> Any:
        score_fn()
        captured["computed_at"] = computed_at
        return summary

    return captured, fake_score, fake_run


def test_recommendations_cli_threads_as_of(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    summary = SimpleNamespace(
        saved=1, as_of_date=_INJECTED, data_source="fixture", error=None
    )
    captured, fake_score, fake_run = _precompute_cli_fakes(summary)
    monkeypatch.setattr(rec_cli, "score_master_target", fake_score)
    monkeypatch.setattr(rec_cli, "run_precompute", fake_run)
    monkeypatch.setattr(rec_cli, "build_default_explainer", lambda: None)

    assert rec_cli.main(["--as-of", "2022-03-31"]) == 0
    assert captured["score_as_of"] == _INJECTED
    assert captured["computed_at"] == _INJECTED_MIDNIGHT


def test_recommendations_cli_default_is_wall_clock(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    summary = SimpleNamespace(
        saved=1, as_of_date=date(2023, 9, 29), data_source="fixture", error=None
    )
    captured, fake_score, fake_run = _precompute_cli_fakes(summary)
    monkeypatch.setattr(rec_cli, "score_master_target", fake_score)
    monkeypatch.setattr(rec_cli, "run_precompute", fake_run)
    monkeypatch.setattr(rec_cli, "build_default_explainer", lambda: None)

    assert rec_cli.main([]) == 0
    assert captured["score_as_of"] is None  # plain scorer — no injected date
    assert captured["computed_at"] is None  # → run_precompute uses datetime.now


# ── regime precompute (deep seam, mirrors recommendations) ────────────────────
def test_regime_cli_threads_as_of(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    summary = SimpleNamespace(
        saved=1, as_of_date=_INJECTED, data_source="fixture", regime="risk_on", error=None
    )
    captured, fake_score, fake_run = _precompute_cli_fakes(summary)
    monkeypatch.setattr(regime_cli, "score_regime_target", fake_score)
    monkeypatch.setattr(regime_cli, "run_regime_precompute", fake_run)

    assert regime_cli.main(["--as-of", "2022-03-31"]) == 0
    assert captured["score_as_of"] == _INJECTED
    assert captured["computed_at"] == _INJECTED_MIDNIGHT

    captured.clear()
    assert regime_cli.main([]) == 0
    assert captured["score_as_of"] is None
    assert captured["computed_at"] is None


# ── advisor (today= seam) ─────────────────────────────────────────────────────
def test_advisor_cli_threads_as_of(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(advisor_cli, "LLMGateway", lambda: object())
    monkeypatch.setattr(advisor_cli, "AdvisorService", lambda _gw: object())

    def fake_run_daily(session: Any, advisor: Any, *, today: date | None = None) -> Any:
        captured["today"] = today
        return SimpleNamespace(saved=1, skipped=0, errors=0)

    monkeypatch.setattr(advisor_cli, "run_daily", fake_run_daily)

    assert advisor_cli.main(["--as-of", "2022-03-31"]) == 0
    assert captured["today"] == _INJECTED
    assert advisor_cli.main([]) == 0
    assert captured["today"] is None


# ── prices (today= seam) ──────────────────────────────────────────────────────
def test_prices_cli_threads_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_fetch_main(args: Any, *, today: date | None = None, **_: Any) -> Any:
        captured["today"] = today
        return prices_cli.FetchSummary(symbols=0, saved=0, errors=0)

    monkeypatch.setattr(prices_cli, "fetch_main", fake_fetch_main)

    assert prices_cli.main(["fetch", "--as-of", "2022-03-31"]) == 0
    assert captured["today"] == _INJECTED
    assert prices_cli.main(["fetch"]) == 0
    assert captured["today"] is None


# ── canonical (as_of= seam) ───────────────────────────────────────────────────
def test_canonical_cli_threads_as_of(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    captured: dict[str, Any] = {}

    def fake_generate(session: Any, *, as_of: date | None = None) -> int:
        captured["as_of"] = as_of
        return 1

    monkeypatch.setattr(canonical, "generate_canonical_reports", fake_generate)

    assert canonical.main(["--as-of", "2022-03-31"]) == 0
    assert captured["as_of"] == _INJECTED
    assert canonical.main([]) == 0
    assert captured["as_of"] is None


# ── paper MTM (on_date + now seam) ────────────────────────────────────────────
def test_paper_mtm_cli_threads_as_of(
    initialised_db: str, monkeypatch: pytest.MonkeyPatch  # noqa: ARG001
) -> None:
    captured: dict[str, Any] = {}

    def fake_run_mtm(
        session: Any, *, on_date: date, now: datetime, provider: Any = None
    ) -> Any:
        captured["on_date"] = on_date
        captured["now"] = now
        return paper_mtm.MtmSummary(accounts=0, points=0, rebalanced=0)

    monkeypatch.setattr(paper_mtm, "run_daily_mtm", fake_run_mtm)

    assert paper_mtm.main(["--as-of", "2022-03-31"]) == 0
    assert captured["on_date"] == _INJECTED
    assert captured["now"] == _INJECTED_MIDNIGHT

    assert paper_mtm.main([]) == 0
    assert captured["on_date"] == datetime.now(UTC).date()  # wall clock today
    assert captured["now"].tzinfo == UTC


# ── data_refresh + news (flag wired into the fetch subparser) ─────────────────
def test_data_refresh_cli_accepts_as_of_flag() -> None:
    args = data_refresh_cli.parse_args(["fetch", "--no-cn-universe", "--as-of", "2022-03-31"])
    assert args.as_of == _INJECTED
    assert data_refresh_cli.parse_args(["fetch"]).as_of is None


def test_news_cli_accepts_as_of_flag() -> None:
    args = news_cli.parse_args(["fetch", "--as-of", "2022-03-31"])
    assert args.as_of == _INJECTED
    assert news_cli.parse_args(["fetch"]).as_of is None

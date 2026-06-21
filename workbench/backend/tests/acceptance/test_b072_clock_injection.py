"""B072 F003 — permanent acceptance invariants for the injectable timer clock.

The clock half of B072 "验收即代码": a CI fast-forward (``--as-of <date>``) must
make each timer run *as of* the injected date deterministically, and omitting it
must be byte-for-byte the old wall-clock behaviour (production zero-regression).

≥3 distinct timers, each with teeth (F004 mutation-checks them — break the as_of
plumb and the matching assertion goes red):
  1. recommendations precompute — scores golden *as of* the injected date (the
     price-load horizon), so an earlier date yields an earlier signal date and a
     genuinely different target (real fast-forward, not a relabel).
  2. canonical report — the injected date dates the report.
  3. news ingest — the injected date anchors the default lookback window.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.backtests import canonical
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.investment_report import InvestmentReportRepository
from workbench_api.news.cli import DEFAULT_LOOKBACK_DAYS, resolve_since
from workbench_api.recommendations.precompute import score_master_target

# workbench/backend/tests/acceptance/<this> → parents[4] is the repo root.
GOLDEN_DIR = Path(__file__).resolve().parents[4] / "data" / "fixtures" / "golden"

# Deterministic golden signal dates (the quarter-end the master scoring lands on
# for a given price-load cutoff). Pinned so the fast-forward has teeth.
_EARLY_AS_OF = date(2021, 12, 31)
_EARLY_SIGNAL = date(2021, 9, 30)
_LATE_AS_OF = date(2023, 12, 31)
_LATE_SIGNAL = date(2023, 9, 29)  # also the default (full-history) signal date


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


# ── timer 1: recommendations precompute fast-forward ─────────────────────────
def test_recommendations_as_of_fast_forwards_golden_target() -> None:
    """``--as-of`` pins the scoring to the injected date: an earlier date lands
    an earlier signal date and a genuinely different (deterministic) target."""

    early = score_master_target(fixture_dir=GOLDEN_DIR, as_of=_EARLY_AS_OF)
    late = score_master_target(fixture_dir=GOLDEN_DIR, as_of=_LATE_AS_OF)

    assert early.as_of_date == _EARLY_SIGNAL
    assert late.as_of_date == _LATE_SIGNAL
    assert early.as_of_date < late.as_of_date  # fast-forward advances the signal
    # A real fast-forward changes the target, not just its label.
    assert early.target_weights != late.target_weights
    assert sum(early.target_weights.values()) == pytest.approx(1.0, abs=1e-3)
    assert sum(late.target_weights.values()) == pytest.approx(1.0, abs=1e-3)


def test_recommendations_as_of_is_deterministic() -> None:
    """Same golden + same injected date → identical target (no wall-clock leak)."""

    first = score_master_target(fixture_dir=GOLDEN_DIR, as_of=_EARLY_AS_OF)
    second = score_master_target(fixture_dir=GOLDEN_DIR, as_of=_EARLY_AS_OF)
    assert first.as_of_date == second.as_of_date == _EARLY_SIGNAL
    assert first.target_weights == second.target_weights


def test_recommendations_default_uses_latest_golden_signal() -> None:
    """Zero regression: no ``as_of`` → today (UTC) cutoff → the latest golden
    signal date (the same target the F001 seed persists)."""

    default = score_master_target(fixture_dir=GOLDEN_DIR)
    assert default.as_of_date == _LATE_SIGNAL
    # Pinning to a date past the golden window matches the default exactly.
    pinned = score_master_target(fixture_dir=GOLDEN_DIR, as_of=_LATE_AS_OF)
    assert default.target_weights == pinned.target_weights


# ── timer 2: canonical report dated by injected as_of ─────────────────────────
def test_canonical_report_dated_by_injected_as_of(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``generate_canonical_reports(as_of=D)`` dates the report at ``D``. The
    heavy real engine is mocked so the test isolates the as_of → report-date
    seam (the engine runs as-of-date-agnostic; the date stamp is the timer
    behaviour under test)."""

    monkeypatch.setattr(
        canonical,
        "run_backtest_job",
        lambda run: {"report_markdown": "# stub", "metrics": {"cagr": 0.1}},  # noqa: ARG005
    )
    injected = date(2022, 3, 31)
    written = canonical.generate_canonical_reports(session, as_of=injected)

    assert written == 1
    report = InvestmentReportRepository(session).get_by_slug(
        f"{canonical.MASTER_STRATEGY_ID}-{injected.isoformat()}"
    )
    assert report is not None
    assert report.as_of_date == injected


# ── timer 3: news lookback window anchored on injected as_of ──────────────────
def test_news_lookback_window_anchored_on_injected_as_of() -> None:
    """``--as-of`` re-anchors the default news lookback window; an explicit
    ``--since`` still wins; omitting both anchors on the real wall clock."""

    injected = date(2022, 3, 31)
    since = resolve_since(None, as_of=injected)
    expected = datetime(2022, 3, 31, tzinfo=UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    assert since == expected

    # Explicit --since overrides the injected anchor.
    assert resolve_since("2026-01-01", as_of=injected) == datetime(
        2026, 1, 1, tzinfo=UTC
    )

    # Zero regression: no as_of → anchored within a second of now (UTC).
    now_default = resolve_since(None)
    drift = abs(
        (now_default - (datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS))).total_seconds()
    )
    assert drift < 5.0

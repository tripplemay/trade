"""B030 F002 — unified-first + FORCE_FIXTURE_PATH source resolution.

Pins the resolution priority of
:func:`trade.data.us_quality_universe.load_prices` /
:func:`trade.data.us_quality_universe.load_fundamentals` after the
F002 cut-over:

1. Explicit ``fixture_dir`` argument always wins.
2. ``FORCE_FIXTURE_PATH=1`` env → default fixture dir.
3. Unified file if it exists on disk.
4. Default fixture dir (fall-back).

Each test isolates the env var via ``monkeypatch.setenv`` /
``delenv`` and the unified file via ``monkeypatch.setattr`` on the
module-level :data:`UNIFIED_PRICES_PATH` / :data:`UNIFIED_FUNDAMENTALS_PATH`
constants so the tests stay deterministic regardless of whether the
B028/B029 backfill has been run on the current checkout.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from trade.data import us_quality_universe as repo
from trade.data.us_quality_universe import (
    DEFAULT_FIXTURE_DIR,
    FORCE_FIXTURE_PATH_ENV,
    FUNDAMENTALS_FILE_NAME,
    PRICES_FILE_NAME,
    _force_fixture_path,
    _resolve_fundamentals_path,
    _resolve_prices_path,
    load_fundamentals,
    load_prices,
)

# ---------------------------------------------------------------------------
# _force_fixture_path / env-var parsing
# ---------------------------------------------------------------------------


def test_force_fixture_path_returns_true_only_for_exact_value_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The env var must be the literal string ``"1"``; ``true``/``yes``
    must NOT trigger the override (avoids accidental fixture-mode in
    CI where someone set ``FORCE_FIXTURE_PATH=true``)."""

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    assert _force_fixture_path() is True

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "true")
    assert _force_fixture_path() is False

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "yes")
    assert _force_fixture_path() is False

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "0")
    assert _force_fixture_path() is False

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "")
    assert _force_fixture_path() is False


def test_force_fixture_path_trims_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``" 1 "`` (with whitespace) still counts as on. Catches a copy-
    paste env file with a trailing newline."""

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, " 1\n")
    assert _force_fixture_path() is True


def test_force_fixture_path_returns_false_when_env_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset env → False (default branch unified-first)."""

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    assert _force_fixture_path() is False


# ---------------------------------------------------------------------------
# _resolve_prices_path — priority 1-4
# ---------------------------------------------------------------------------


def test_resolve_prices_path_explicit_fixture_dir_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Priority 1 — explicit ``fixture_dir`` overrides the env var
    AND the unified file."""

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    # Spoof a fake unified file that exists.
    fake_unified = tmp_path / "spoofed_unified.csv"
    fake_unified.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", fake_unified)
    # Create the explicit fixture dir.
    custom = tmp_path / "my_b025_fixture"
    custom.mkdir()
    (custom / PRICES_FILE_NAME).write_text("dummy", encoding="utf-8")

    resolved = _resolve_prices_path(custom)
    assert resolved == custom / PRICES_FILE_NAME


def test_resolve_prices_path_force_fixture_env_overrides_unified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Priority 2 — ``FORCE_FIXTURE_PATH=1`` overrides a present
    unified file. Pinned for the B025 deterministic test guarantee."""

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    # Spoof a unified file that exists.
    fake_unified = tmp_path / "spoofed_unified.csv"
    fake_unified.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", fake_unified)

    resolved = _resolve_prices_path(None)
    assert resolved == DEFAULT_FIXTURE_DIR / PRICES_FILE_NAME
    # Confirm the unified file existed — sanity check the test setup.
    assert fake_unified.exists()


def test_resolve_prices_path_unified_preferred_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Priority 3 — when unified exists and env unset, return unified."""

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    fake_unified = tmp_path / "spoofed_unified.csv"
    fake_unified.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", fake_unified)

    resolved = _resolve_prices_path(None)
    assert resolved == fake_unified


def test_resolve_prices_path_falls_back_to_default_fixture_when_unified_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Priority 4 — unified missing → default fixture dir (the B025
    synthetic CSV that ships with the repo)."""

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    missing_unified = tmp_path / "does_not_exist.csv"
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", missing_unified)

    resolved = _resolve_prices_path(None)
    assert resolved == DEFAULT_FIXTURE_DIR / PRICES_FILE_NAME


# ---------------------------------------------------------------------------
# _resolve_fundamentals_path — same four-tier semantics
# ---------------------------------------------------------------------------


def test_resolve_fundamentals_path_explicit_fixture_dir_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    fake_unified = tmp_path / "spoofed_unified.csv"
    fake_unified.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", fake_unified)
    custom = tmp_path / "my_b025_fixture"
    custom.mkdir()
    (custom / FUNDAMENTALS_FILE_NAME).write_text("dummy", encoding="utf-8")

    resolved = _resolve_fundamentals_path(custom)
    assert resolved == custom / FUNDAMENTALS_FILE_NAME


def test_resolve_fundamentals_path_force_fixture_env_overrides_unified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    fake_unified = tmp_path / "spoofed_unified.csv"
    fake_unified.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", fake_unified)

    resolved = _resolve_fundamentals_path(None)
    assert resolved == DEFAULT_FIXTURE_DIR / FUNDAMENTALS_FILE_NAME


def test_resolve_fundamentals_path_unified_preferred_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    fake_unified = tmp_path / "spoofed_unified.csv"
    fake_unified.write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", fake_unified)

    resolved = _resolve_fundamentals_path(None)
    assert resolved == fake_unified


def test_resolve_fundamentals_path_falls_back_to_default_fixture_when_unified_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    missing_unified = tmp_path / "does_not_exist.csv"
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", missing_unified)

    resolved = _resolve_fundamentals_path(None)
    assert resolved == DEFAULT_FIXTURE_DIR / FUNDAMENTALS_FILE_NAME


# ---------------------------------------------------------------------------
# load_prices end-to-end with spoofed unified CSV
# ---------------------------------------------------------------------------


def _write_minimal_prices_csv(path: Path, ticker: str, value: float) -> None:
    """Write a 1-row prices CSV that matches the unified schema."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=(
                "date", "ticker", "open", "high", "low",
                "close", "adj_close", "volume",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "2025-02-04",
                "ticker": ticker,
                "open": str(value - 1),
                "high": str(value + 1),
                "low": str(value - 2),
                "close": str(value),
                "adj_close": str(value),
                "volume": "1000000",
            }
        )


def test_load_prices_reads_unified_by_default_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """E2E: spoof a unified CSV with a known sentinel ticker that the
    real B025 fixture doesn't have. ``load_prices()`` (default) must
    return the sentinel — proves we read unified, not fixture."""

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    spoofed_unified = tmp_path / "unified_prices.csv"
    _write_minimal_prices_csv(spoofed_unified, "ZTEST_F002", 100.0)
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", spoofed_unified)

    frame = load_prices()
    tickers = set(frame["ticker"].astype(str).tolist())
    assert "ZTEST_F002" in tickers
    # Sanity: B025 fixture tickers should NOT be in this slice (unified
    # has only the sentinel).
    assert tickers == {"ZTEST_F002"}


def test_load_prices_reads_fixture_when_force_fixture_path_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``FORCE_FIXTURE_PATH=1`` makes ``load_prices()`` ignore the
    unified file (even if present) and use the B025 fixture."""

    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    spoofed_unified = tmp_path / "unified_prices.csv"
    _write_minimal_prices_csv(spoofed_unified, "ZTEST_F002", 100.0)
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", spoofed_unified)

    frame = load_prices()
    tickers = set(frame["ticker"].astype(str).tolist())
    # B025 fixture tickers (sample) must be present.
    assert "AAPL" in tickers
    # The sentinel from the spoofed unified must NOT leak in.
    assert "ZTEST_F002" not in tickers


def test_load_prices_falls_back_to_fixture_when_unified_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unified missing AND no env override → fall back to B025 fixture.

    Mirrors the CI environment where ``data/snapshots/`` is git-
    ignored and not present on a fresh checkout.
    """

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    monkeypatch.setattr(
        repo, "UNIFIED_PRICES_PATH", tmp_path / "does_not_exist.csv"
    )

    frame = load_prices()
    tickers = set(frame["ticker"].astype(str).tolist())
    assert "AAPL" in tickers  # B025 fixture default ticker


# ---------------------------------------------------------------------------
# load_fundamentals end-to-end with spoofed unified CSV
# ---------------------------------------------------------------------------


def _write_minimal_fundamentals_csv(path: Path, ticker: str) -> None:
    """Write a 1-row fundamentals CSV matching the 12-col schema."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=(
                "report_date", "ticker", "fiscal_quarter",
                "fiscal_quarter_end",
                "roe", "gross_margin", "fcf_yield", "debt_to_assets",
                "pe", "pb", "ev_ebitda", "earnings_yield",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "report_date": "2025-02-04",
                "ticker": ticker,
                "fiscal_quarter": "2024Q4",
                "fiscal_quarter_end": "2024-12-31",
                "roe": "0.20",
                "gross_margin": "0.40",
                "fcf_yield": "0.05",
                "debt_to_assets": "0.30",
                "pe": "20.0",
                "pb": "5.0",
                "ev_ebitda": "15.0",
                "earnings_yield": "0.05",
            }
        )


def test_load_fundamentals_reads_unified_by_default_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    spoofed_unified = tmp_path / "unified_fundamentals.csv"
    _write_minimal_fundamentals_csv(spoofed_unified, "ZTEST_FUND")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", spoofed_unified)

    frame = load_fundamentals()
    tickers = set(frame["ticker"].astype(str).tolist())
    assert tickers == {"ZTEST_FUND"}


def test_load_fundamentals_reads_fixture_when_force_fixture_path_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(FORCE_FIXTURE_PATH_ENV, "1")
    spoofed_unified = tmp_path / "unified_fundamentals.csv"
    _write_minimal_fundamentals_csv(spoofed_unified, "ZTEST_FUND")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", spoofed_unified)

    frame = load_fundamentals()
    tickers = set(frame["ticker"].astype(str).tolist())
    # B025 fixture has AAPL etc.; spoofed sentinel must NOT leak in.
    assert "AAPL" in tickers
    assert "ZTEST_FUND" not in tickers


def test_load_fundamentals_falls_back_to_fixture_when_unified_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    monkeypatch.setattr(
        repo, "UNIFIED_FUNDAMENTALS_PATH", tmp_path / "does_not_exist.csv"
    )

    frame = load_fundamentals()
    tickers = set(frame["ticker"].astype(str).tolist())
    assert "AAPL" in tickers


# ---------------------------------------------------------------------------
# PIT semantics preserved across the source switch
# ---------------------------------------------------------------------------


def test_load_prices_pit_filter_works_against_unified_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ``as_of`` filter must apply regardless of which source is
    consulted. Catches a regression where the unified branch forgot
    to ``date <= as_of``."""

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    spoofed_unified = tmp_path / "unified_prices.csv"
    _write_minimal_prices_csv(spoofed_unified, "ZTEST_PIT", 100.0)
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", spoofed_unified)

    # The spoofed row has date 2025-02-04. as_of=2020-12-31 must drop it.
    frame = load_prices(as_of=date(2020, 12, 31))
    assert frame.empty


def test_load_fundamentals_pit_filter_works_against_unified_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    spoofed_unified = tmp_path / "unified_fundamentals.csv"
    _write_minimal_fundamentals_csv(spoofed_unified, "ZTEST_PIT_F")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", spoofed_unified)

    # Spoofed report_date is 2025-02-04; as_of=2020-12-31 drops it.
    frame = load_fundamentals(as_of=date(2020, 12, 31))
    assert frame.empty


# ---------------------------------------------------------------------------
# Backward-compat: explicit fixture_dir argument keeps working
# ---------------------------------------------------------------------------


def test_load_prices_explicit_fixture_dir_argument_still_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B025 deterministic tests use ``load_prices(fixture_dir=...)``
    to pin to a specific fixture checkout. F002 must not break that
    parameter even with the unified branch active."""

    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    # Spoof a unified file that has a wrong sentinel.
    bogus_unified = tmp_path / "bogus_unified.csv"
    _write_minimal_prices_csv(bogus_unified, "WRONG_TICKER", 999.0)
    monkeypatch.setattr(repo, "UNIFIED_PRICES_PATH", bogus_unified)

    # Build a custom fixture dir with a different sentinel.
    custom = tmp_path / "my_b025_fixture"
    custom.mkdir()
    _write_minimal_prices_csv(custom / PRICES_FILE_NAME, "CUSTOM_TICKER", 50.0)

    frame = load_prices(fixture_dir=custom)
    tickers = set(frame["ticker"].astype(str).tolist())
    assert tickers == {"CUSTOM_TICKER"}


def test_load_fundamentals_explicit_fixture_dir_argument_still_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FORCE_FIXTURE_PATH_ENV, raising=False)
    bogus_unified = tmp_path / "bogus_unified.csv"
    _write_minimal_fundamentals_csv(bogus_unified, "WRONG_F")
    monkeypatch.setattr(repo, "UNIFIED_FUNDAMENTALS_PATH", bogus_unified)

    custom = tmp_path / "my_b025_fixture"
    custom.mkdir()
    _write_minimal_fundamentals_csv(custom / FUNDAMENTALS_FILE_NAME, "CUSTOM_F")

    frame = load_fundamentals(fixture_dir=custom)
    tickers = set(frame["ticker"].astype(str).tolist())
    assert tickers == {"CUSTOM_F"}


# ---------------------------------------------------------------------------
# Module-level path constants pinned (catches refactor drift)
# ---------------------------------------------------------------------------


def test_unified_paths_match_loader_paths() -> None:
    """The unified paths declared here must match the ones declared in
    :mod:`trade.data.loader`. Drift here means the strategy layer
    and the lower-level loader read from different files."""

    from trade.data import loader

    assert repo.UNIFIED_PRICES_PATH == loader.UNIFIED_PRICES_PATH
    assert repo.UNIFIED_FUNDAMENTALS_PATH == loader.UNIFIED_FUNDAMENTALS_PATH


def test_force_fixture_path_env_constant_pinned() -> None:
    """Pin the env-var name. Renaming this constant breaks every B025
    deterministic test fixture that uses it."""

    assert FORCE_FIXTURE_PATH_ENV == "FORCE_FIXTURE_PATH"

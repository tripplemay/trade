"""B045 F003 — granular data_source marking + real-daily sleeve scoring.

Two halves:

* :func:`_classify_data_source` / :func:`_load_scoring_records` units pin the
  three-state honesty contract (``real`` / ``mixed`` / ``fixture``) and the
  VM-vs-fixture record source selection.
* An integration test feeds a synthetic **real** unified daily-prices CSV
  (via the B045 F002 ``WORKBENCH_DATA_ROOT`` override) through the real
  ``score_master_target`` and proves the B044 S3 gap is gone: risk_parity —
  ``stubbed_data_unavailable`` on the monthly fixture — now scores, and the run
  is marked ``mixed`` (real prices, us_quality still stubbed for lack of
  fundamentals) rather than the blanket ``fixture``.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest
from trade.data.data_root import (  # type: ignore[import-untyped]
    DATA_ROOT_ENV,
    UNIFIED_FUNDAMENTALS_RELPATH,
    UNIFIED_PRICES_RELPATH,
)
from trade.data.us_quality_universe import (  # type: ignore[import-untyped]
    DEFAULT_FIXTURE_DIR,
)

from workbench_api.db.models.recommendation_snapshot import (
    DATA_SOURCE_FIXTURE,
    DATA_SOURCE_MIXED,
    DATA_SOURCE_REAL,
)
from workbench_api.recommendations.precompute import (
    _PRICES_SOURCE_FIXTURE,
    _PRICES_SOURCE_REAL,
    _SLEEVE_STATUS_FALLBACK,
    _SLEEVE_STATUS_SCORED,
    _SLEEVE_STATUS_STUBBED,
    _classify_data_source,
    _load_scoring_records,
    _resolved_to_pure_defensive,
    score_master_target,
)

# risk_parity risk assets (SGOV is the defensive asset, excluded from vol).
_ETF_UNIVERSE = ("SPY", "VEA", "AGG", "GLD", "SGOV", "EEM")

# The full-real test needs the B025 us_quality fixture (prices + fundamentals +
# universe.csv). It exists in an editable trade install (local dev / repo CI) but
# NOT when trade is wheel-installed (the workbench backend CI venv / the VM),
# where ``data/fixtures`` isn't bundled. Skip there — the full-real path is
# exercised here when available and L2-verified on the VM.
_FIXTURE_AVAILABLE = (DEFAULT_FIXTURE_DIR / "prices_daily.csv").exists()


# ---------------------------------------------------------------------------
# _classify_data_source — three-state honesty
# ---------------------------------------------------------------------------


def test_classify_fixture_when_prices_are_fixture() -> None:
    status = {"momentum": _SLEEVE_STATUS_SCORED, "risk_parity": _SLEEVE_STATUS_SCORED}
    assert _classify_data_source(_PRICES_SOURCE_FIXTURE, status) == DATA_SOURCE_FIXTURE


def test_classify_real_when_real_prices_and_all_scored() -> None:
    status = {
        "momentum": _SLEEVE_STATUS_SCORED,
        "risk_parity": _SLEEVE_STATUS_SCORED,
        "satellite_us_quality": _SLEEVE_STATUS_SCORED,
        "satellite_hk_china": _SLEEVE_STATUS_SCORED,
    }
    assert _classify_data_source(_PRICES_SOURCE_REAL, status) == DATA_SOURCE_REAL


def test_classify_mixed_when_real_prices_but_a_sleeve_stubbed() -> None:
    status = {
        "momentum": _SLEEVE_STATUS_SCORED,
        "risk_parity": _SLEEVE_STATUS_SCORED,
        "satellite_us_quality": _SLEEVE_STATUS_STUBBED,
    }
    assert _classify_data_source(_PRICES_SOURCE_REAL, status) == DATA_SOURCE_MIXED


def test_classify_mixed_when_real_prices_but_a_sleeve_fell_back() -> None:
    """B111 F002 — a sleeve that ran but parked 100% in the defensive asset
    (P0-2) degrades the run to ``mixed``; the metadata must never say ``real``
    while a sleeve holds 0 risk exposure."""

    status = {
        "momentum": _SLEEVE_STATUS_SCORED,
        "risk_parity": _SLEEVE_STATUS_SCORED,
        "satellite_us_quality": _SLEEVE_STATUS_FALLBACK,
        "satellite_hk_china": _SLEEVE_STATUS_SCORED,
    }
    assert _classify_data_source(_PRICES_SOURCE_REAL, status) == DATA_SOURCE_MIXED


def test_resolved_to_pure_defensive_detects_defensive_only_sleeve() -> None:
    # 100% the defensive asset → a fall-back (zero risk exposure).
    assert _resolved_to_pure_defensive({"SGOV": 1.0}, "SGOV") is True
    assert _resolved_to_pure_defensive({}, "SGOV") is True
    assert _resolved_to_pure_defensive({"SGOV": 1.0, "SPY": 0.0}, "SGOV") is True
    # Any real risk holding → a genuine allocation, not a fall-back.
    assert _resolved_to_pure_defensive({"SGOV": 0.5, "SPY": 0.5}, "SGOV") is False
    # A sleeve's own non-master defensive (e.g. momentum → AGG bonds) is a real
    # position from the master's perspective, not a defensive park.
    assert _resolved_to_pure_defensive({"AGG": 1.0}, "SGOV") is False


# ---------------------------------------------------------------------------
# _load_scoring_records — VM real vs fixture fall-back
# ---------------------------------------------------------------------------


def _business_days(start: date, count: int) -> list[date]:
    out: list[date] = []
    cursor = start
    while len(out) < count:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


def _write_daily_prices(root: Path, symbols: tuple[str, ...], days: list[date]) -> None:
    """Write a unified daily-prices CSV with varying (vol > 0) adj_close."""

    path = root.joinpath(*UNIFIED_PRICES_RELPATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
        )
        for offset, symbol in enumerate(symbols):
            for i, day in enumerate(days):
                px = 100 + offset + (i % 5)  # always > 0, oscillates → variance > 0
                writer.writerow(
                    [day.isoformat(), symbol, px, px + 1, px - 1, px, px, 1_000_000]
                )


def test_load_scoring_records_fixture_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    records, source = _load_scoring_records()
    assert source == _PRICES_SOURCE_FIXTURE
    assert len(records) > 0


def test_load_scoring_records_real_when_vm_unified_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    _write_daily_prices(tmp_path, ("SPY", "AGG"), _business_days(date(2025, 1, 1), 10))
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    records, source = _load_scoring_records()
    assert source == _PRICES_SOURCE_REAL
    assert {bar.symbol for bar in records} == {"SPY", "AGG"}


def test_load_scoring_records_falls_back_when_vm_root_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Env set but no unified file → fixture fall-back, not a crash / empty."""

    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "empty_root"))

    records, source = _load_scoring_records()
    assert source == _PRICES_SOURCE_FIXTURE
    assert len(records) > 0


# ---------------------------------------------------------------------------
# score_master_target — real-daily path eliminates the B044 S3 stub
# ---------------------------------------------------------------------------


def test_score_master_target_fixture_path_stubs_risk_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline contrast (env unset): the monthly fixture has no daily vol
    history, so risk_parity stubs and the run is marked ``fixture``."""

    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    result = score_master_target()
    assert result.master_meta["data_source"] == DATA_SOURCE_FIXTURE
    assert result.master_meta["prices_source"] == _PRICES_SOURCE_FIXTURE
    assert result.master_meta["sleeve_status"]["risk_parity"] == _SLEEVE_STATUS_STUBBED


def test_score_master_target_real_daily_path_scores_risk_parity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With real daily prices for the ETF universe, risk_parity gets its 120-bar
    vol history and scores — the B044 S3 ``sleeve_unavailable`` gap is gone.
    us_quality still stubs (no fundamentals here) → the run is ``mixed``, marked
    honestly rather than blanket ``fixture``."""

    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    days = _business_days(date(2024, 1, 2), 500)
    _write_daily_prices(tmp_path, _ETF_UNIVERSE, days)
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    result = score_master_target()

    assert result.master_meta["prices_source"] == _PRICES_SOURCE_REAL
    # The S3 elimination: risk_parity is no longer stubbed.
    assert result.master_meta["sleeve_status"]["risk_parity"] == _SLEEVE_STATUS_SCORED
    # Real prices + (us_quality stubbed for lack of fundamentals) → mixed, honest.
    assert result.master_meta["data_source"] in {DATA_SOURCE_REAL, DATA_SOURCE_MIXED}
    assert result.master_meta["data_source"] != DATA_SOURCE_FIXTURE
    assert sum(result.target_weights.values()) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.skipif(
    not _FIXTURE_AVAILABLE,
    reason="B025 fixture absent (trade wheel-installed without data/fixtures); "
    "full-real path is L2-verified on the VM",
)
def test_score_master_target_full_real_reaches_data_source_real(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The full real path: real equity prices + fundamentals (the B025 us_quality
    data, served through the F002 ``WORKBENCH_DATA_ROOT`` override) make
    us_quality score, and synthetic daily ETF bars make risk_parity score → every
    implemented sleeve scores → ``data_source=real`` (B045 F004 #1 goal: real
    fundamentals → us_quality off the stub). On the VM the same wiring reads the
    F001 refresh's live SEC fundamentals instead of this fixture."""

    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)

    # Unified prices = the B025 equity rows (real us_quality data) + synthetic
    # daily ETF bars (last 250 fixture dates) so risk_parity has vol history.
    body = list(csv.reader((DEFAULT_FIXTURE_DIR / "prices_daily.csv").open(encoding="utf-8")))
    header, rows = body[0], body[1:]
    # Production's refresh job prices only ``price_universe()`` = ETFs + the 27
    # real ``equity_universe`` tickers; the synthetic ZQ* padding names in the
    # B025 fixture universe are NOT priced on the VM (so us_quality never picks
    # them there). Drop their price rows here so the synthetic unified CSV
    # matches production — otherwise us_quality could select a ZQ* name absent
    # from the master records and the whole sleeve would (correctly) fall back.
    rows = [r for r in rows if not r[1].startswith("ZQ")]
    # A wide window so every sleeve has full history at the (earlier) quarter-end
    # signal date — hk_china's regional gate needs a 200-day MA, so the last 250
    # days alone leave its ~Q3 signal date short of history.
    fixture_days = sorted({r[0] for r in rows})[-600:]
    unified_prices = tmp_path.joinpath(*UNIFIED_PRICES_RELPATH)
    unified_prices.parent.mkdir(parents=True, exist_ok=True)
    with unified_prices.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
        for offset, symbol in enumerate(_ETF_UNIVERSE):
            for i, day in enumerate(fixture_days):
                px = 100 + offset + (i % 5)
                writer.writerow([day, symbol, px, px + 1, px - 1, px, px, 1_000_000])
        # HK-China ETFs, steadily up-trending so the regional gate (price >
        # 200D MA + positive composite momentum) passes and the sleeve holds
        # real tickers → all four sleeves score → data_source can reach 'real'.
        for offset, symbol in enumerate(("MCHI", "FXI", "KWEB", "ASHR")):
            for i, day in enumerate(fixture_days):
                px = 50 + offset + i * 0.2
                writer.writerow([day, symbol, px, px + 1, px - 1, px, px, 1_000_000])

    # Unified fundamentals = the B025 fixture fundamentals (real us_quality ratios).
    unified_fund = tmp_path.joinpath(*UNIFIED_FUNDAMENTALS_RELPATH)
    unified_fund.parent.mkdir(parents=True, exist_ok=True)
    unified_fund.write_bytes((DEFAULT_FIXTURE_DIR / "fundamentals.csv").read_bytes())

    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    result = score_master_target()

    status = result.master_meta["sleeve_status"]
    assert result.master_meta["prices_source"] == _PRICES_SOURCE_REAL
    assert status["risk_parity"] == _SLEEVE_STATUS_SCORED
    assert status["satellite_us_quality"] == _SLEEVE_STATUS_SCORED
    assert _SLEEVE_STATUS_STUBBED not in status.values()
    assert result.master_meta["data_source"] == DATA_SOURCE_REAL


@pytest.mark.skipif(
    not _FIXTURE_AVAILABLE,
    reason="B025 fixture absent (trade wheel-installed without data/fixtures); "
    "the real-price fall-back path is L2-verified on the VM",
)
def test_score_master_target_marks_fallback_not_scored_on_real_prices(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """B111 F002 (P0-2) — a sleeve that RUNS on real prices but resolves to 100%
    the defensive asset (here hk_china, whose ETFs are absent from the unified
    CSV → empty signal → SGOV) must be marked ``fallback`` (never ``scored``),
    emit a warning, and drag ``data_source`` off ``real`` to ``mixed``. This is
    the exact P0-2 blind spot: 0-holdings reported as scored/real."""

    monkeypatch.delenv("FORCE_FIXTURE_PATH", raising=False)
    body = list(csv.reader((DEFAULT_FIXTURE_DIR / "prices_daily.csv").open(encoding="utf-8")))
    header, rows = body[0], body[1:]
    rows = [r for r in rows if not r[1].startswith("ZQ")]
    fixture_days = sorted({r[0] for r in rows})[-600:]
    # Real prices for the ETF universe + us_quality equities, but NO HK-China
    # ETF rows → the hk_china sleeve runs and falls back to the defensive asset.
    unified_prices = tmp_path.joinpath(*UNIFIED_PRICES_RELPATH)
    unified_prices.parent.mkdir(parents=True, exist_ok=True)
    with unified_prices.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
        for offset, symbol in enumerate(_ETF_UNIVERSE):
            for i, day in enumerate(fixture_days):
                px = 100 + offset + (i % 5)
                writer.writerow([day, symbol, px, px + 1, px - 1, px, px, 1_000_000])
    unified_fund = tmp_path.joinpath(*UNIFIED_FUNDAMENTALS_RELPATH)
    unified_fund.parent.mkdir(parents=True, exist_ok=True)
    unified_fund.write_bytes((DEFAULT_FIXTURE_DIR / "fundamentals.csv").read_bytes())
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    with caplog.at_level(logging.WARNING):
        result = score_master_target()

    status = result.master_meta["sleeve_status"]
    assert result.master_meta["prices_source"] == _PRICES_SOURCE_REAL
    # The empty sleeve is a fall-back, NOT a scored allocation.
    assert status["satellite_hk_china"] == _SLEEVE_STATUS_FALLBACK
    assert status["satellite_hk_china"] != _SLEEVE_STATUS_SCORED
    # A warning is emitted so monitoring can see the parked sleeve.
    assert "recommendations_precompute_sleeve_fallback" in caplog.text
    # Real prices + a fall-back sleeve → mixed, never real.
    assert result.master_meta["data_source"] == DATA_SOURCE_MIXED

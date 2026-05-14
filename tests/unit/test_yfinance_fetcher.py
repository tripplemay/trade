"""Unit tests for the opt-in yfinance fetcher helper.

Research-only: every yfinance boundary is patched so the test suite never opens a
real socket and never reaches Yahoo Finance.
"""

from __future__ import annotations

import csv
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from scripts.fetch_yfinance_regime_adaptive_csvs import (
    COVERAGE_THRESHOLD,
    DEFAULT_ALLOW_SHORT_HISTORY,
    EXPECTED_YF_COLUMNS,
    MANUAL_CONFIRM_FLAG,
    OUTPUT_CSV_HEADER,
    SHORT_HISTORY_INCEPTIONS,
    FetchRequest,
    YFinanceFetcherError,
    _expected_business_days,
    build_arg_parser,
    fetch_yfinance_regime_adaptive_csvs,
    main,
)
from trade.strategies.regime_adaptive.snapshot import REQUIRED_TICKERS

FETCHER_MODULE = "scripts.fetch_yfinance_regime_adaptive_csvs"
FETCHER_SOURCE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "fetch_yfinance_regime_adaptive_csvs.py"
)


@dataclass
class _FetchInvocation:
    symbol: str
    start: date
    end: date


def _make_canned_history(
    start: date,
    end: date,
    *,
    base_price: float = 100.0,
    columns: tuple[str, ...] = EXPECTED_YF_COLUMNS,
    extra_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    business_days = pd.bdate_range(start=start.isoformat(), end=end.isoformat())
    n = len(business_days)
    closes = [base_price + 0.05 * i for i in range(n)]
    opens = [close - 0.5 for close in closes]
    highs = [close + 0.5 for close in closes]
    lows = [close - 1.0 for close in closes]
    volumes = [1_000_000 for _ in range(n)]
    column_values: dict[str, list[float] | list[int]] = {
        "Open": opens,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": volumes,
    }
    data = {name: column_values[name] for name in columns if name in column_values}
    for extra in extra_columns:
        data[extra] = [0.0] * n
    frame = pd.DataFrame(data, index=business_days)
    frame.index.name = "Date"
    return frame


SGOV_INCEPTION = date(2020, 5, 28)


def _default_history_builder(symbol: str) -> Callable[[date, date], pd.DataFrame]:
    """Build per-ticker canned DataFrames that mirror real Yahoo behavior.

    SGOV is treated as having no data before its real-world inception
    (2020-05-28) regardless of the requested start date; other tickers always
    cover the requested window in full.
    """

    def _build(start: date, end: date) -> pd.DataFrame:
        effective_start = start
        if symbol == "SGOV" and effective_start < SGOV_INCEPTION:
            effective_start = SGOV_INCEPTION
        if effective_start > end:
            return pd.DataFrame(
                columns=list(EXPECTED_YF_COLUMNS),
                index=pd.DatetimeIndex([], name="Date"),
            )
        return _make_canned_history(effective_start, end)

    return _build


def _install_mock_history(
    monkeypatch: pytest.MonkeyPatch,
    *,
    builders: dict[str, Callable[[date, date], pd.DataFrame]] | None = None,
    raise_for: dict[str, BaseException] | None = None,
    invocations: list[_FetchInvocation] | None = None,
) -> None:
    raise_for = raise_for or {}
    overrides = builders or {}

    def _fake(symbol: str, start: date, end: date) -> pd.DataFrame:
        if invocations is not None:
            invocations.append(_FetchInvocation(symbol=symbol, start=start, end=end))
        if symbol in raise_for:
            raise raise_for[symbol]
        builder = overrides.get(symbol, _default_history_builder(symbol))
        return builder(start, end)

    monkeypatch.setattr(f"{FETCHER_MODULE}._fetch_ticker_history", _fake)


def _block_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in yfinance fetcher tests")

    monkeypatch.setattr(socket, "socket", _refuse)


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())
    return fieldnames, rows


def test_required_tickers_cover_regime_adaptive_universe() -> None:
    assert REQUIRED_TICKERS == ("SPY", "QQQ", "VEA", "VWO", "IEF", "TLT", "GLD", "DBC", "SGOV")


def test_sgov_inception_constant_is_documented() -> None:
    assert SHORT_HISTORY_INCEPTIONS["SGOV"] == date(2020, 5, 28)
    assert frozenset({"SGOV"}) == DEFAULT_ALLOW_SHORT_HISTORY


def test_expected_business_days_counts_weekdays_only() -> None:
    # 2024-01-01 (Mon) through 2024-01-14 (Sun) → 10 weekdays.
    assert _expected_business_days(date(2024, 1, 1), date(2024, 1, 14)) == 10


def test_happy_path_writes_nine_uppercase_csvs_with_canonical_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    invocations: list[_FetchInvocation] = []
    _install_mock_history(monkeypatch, invocations=invocations)

    summary = fetch_yfinance_regime_adaptive_csvs(
        FetchRequest(
            output_dir=tmp_path / "staging",
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    assert len(invocations) == len(REQUIRED_TICKERS), "expected one yfinance call per ticker"
    assert {inv.symbol for inv in invocations} == set(REQUIRED_TICKERS)
    for invocation in invocations:
        if invocation.symbol == "SGOV":
            assert invocation.start == date(2020, 5, 28)
        else:
            assert invocation.start == date(2018, 1, 1)
        assert invocation.end == date(2025, 12, 31)
    assert {result.ticker for result in summary.results} == set(REQUIRED_TICKERS)
    for result in summary.results:
        assert result.output_file.name == f"{result.ticker}.csv"
        assert result.output_file.exists()
        fieldnames, rows = _read_csv(result.output_file)
        assert fieldnames == OUTPUT_CSV_HEADER
        assert rows, f"{result.ticker} CSV must have at least one row"
        if result.ticker == "SGOV":
            assert result.short_history_exempt is True
            assert result.first_date >= date(2020, 5, 28)
        else:
            assert result.short_history_exempt is False
            assert result.first_date >= date(2018, 1, 1)
            assert result.coverage_ratio >= COVERAGE_THRESHOLD


def test_missing_manual_confirmation_refused(tmp_path: Path) -> None:
    with pytest.raises(YFinanceFetcherError, match="manual confirmation"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=False,
            )
        )


def test_yfinance_exception_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    _install_mock_history(
        monkeypatch,
        raise_for={"SPY": RuntimeError("yahoo returned 503")},
    )

    with pytest.raises(YFinanceFetcherError, match="yfinance.Ticker"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_empty_dataframe_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    builders: dict[str, Callable[[date, date], pd.DataFrame]] = {}
    builders["QQQ"] = lambda _start, _end: pd.DataFrame(
        columns=list(EXPECTED_YF_COLUMNS),
        index=pd.DatetimeIndex([], name="Date"),
    )
    _install_mock_history(monkeypatch, builders=builders)

    with pytest.raises(YFinanceFetcherError, match="empty DataFrame for QQQ"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_schema_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    builders: dict[str, Callable[[date, date], pd.DataFrame]] = {}
    # Drop "Open" column to simulate yfinance response missing a required field.
    builders["VEA"] = lambda start, end: _make_canned_history(
        start, end, columns=("High", "Low", "Close", "Volume")
    )
    _install_mock_history(monkeypatch, builders=builders)

    with pytest.raises(YFinanceFetcherError, match="missing required columns"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_non_sgov_short_history_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    builders: dict[str, Callable[[date, date], pd.DataFrame]] = {}
    # Return only the last six months for SPY — clearly below the 95% gate.
    builders["SPY"] = lambda _start, end: _make_canned_history(date(2025, 7, 1), end)
    _install_mock_history(monkeypatch, builders=builders)

    with pytest.raises(YFinanceFetcherError, match="insufficient coverage for SPY"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_sgov_short_history_accepted_under_default_allowance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    invocations: list[_FetchInvocation] = []
    _install_mock_history(monkeypatch, invocations=invocations)

    summary = fetch_yfinance_regime_adaptive_csvs(
        FetchRequest(
            output_dir=tmp_path / "staging",
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    sgov_invocations = [inv for inv in invocations if inv.symbol == "SGOV"]
    assert len(sgov_invocations) == 1
    assert sgov_invocations[0].start == date(2020, 5, 28)
    sgov_result = next(r for r in summary.results if r.ticker == "SGOV")
    assert sgov_result.short_history_exempt is True
    assert sgov_result.first_date >= date(2020, 5, 28)


def test_sgov_short_history_rejected_when_allowance_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    _install_mock_history(monkeypatch)

    with pytest.raises(YFinanceFetcherError, match="insufficient coverage for SGOV"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
                allow_short_history=frozenset(),
            )
        )


def test_date_to_before_date_from_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(YFinanceFetcherError, match="precedes date_from"):
        fetch_yfinance_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2025, 1, 1),
                date_to=date(2024, 1, 1),
                manual_confirmation=True,
            )
        )


def test_cli_main_returns_zero_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _block_socket(monkeypatch)
    _install_mock_history(monkeypatch)

    rc = main(
        [
            "--output-dir",
            str(tmp_path / "staging"),
            "--from",
            "2018-01-01",
            "--to",
            "2025-12-31",
            MANUAL_CONFIRM_FLAG,
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "yfinance fetch summary" in captured.out
    assert "research-only" in captured.out.lower()


def test_cli_main_without_manual_confirmation_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _trip(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("yfinance must not be called when manual flag is missing")

    monkeypatch.setattr(f"{FETCHER_MODULE}._fetch_ticker_history", _trip)

    rc = main(
        [
            "--output-dir",
            str(tmp_path / "staging"),
            "--from",
            "2018-01-01",
            "--to",
            "2025-12-31",
        ]
    )

    assert rc == 2
    captured = capsys.readouterr()
    assert "manual confirmation" in captured.err.lower()


def test_arg_parser_short_history_parses_comma_list(tmp_path: Path) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--output-dir",
            str(tmp_path),
            "--allow-short-history",
            "sgov,foo,bar",
            MANUAL_CONFIRM_FLAG,
        ]
    )
    assert args.allow_short_history == frozenset({"SGOV", "FOO", "BAR"})


def test_arg_parser_short_history_empty_disables_allowance(tmp_path: Path) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--output-dir",
            str(tmp_path),
            "--allow-short-history",
            "",
            MANUAL_CONFIRM_FLAG,
        ]
    )
    assert args.allow_short_history == frozenset()


def test_output_csv_data_is_well_formed_floats_and_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    _install_mock_history(monkeypatch)

    summary = fetch_yfinance_regime_adaptive_csvs(
        FetchRequest(
            output_dir=tmp_path / "staging",
            date_from=date(2024, 1, 1),
            date_to=date(2024, 3, 31),
            manual_confirmation=True,
        )
    )

    sample = next(r for r in summary.results if r.ticker == "QQQ")
    fieldnames, rows = _read_csv(sample.output_file)
    assert fieldnames == OUTPUT_CSV_HEADER
    for row in rows:
        date.fromisoformat(row["date"])  # validates ISO format
        for key in ("open", "high", "low", "close", "adjusted_close"):
            float(row[key])
        int(row["volume"])
        # adjusted_close mirrors close because auto_adjust=True at the yfinance call site.
        assert row["close"] == row["adjusted_close"]
    assert [row["date"] for row in rows] == sorted(row["date"] for row in rows)


def test_no_real_socket_usage_under_default_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fetcher must never open a real socket when its yfinance boundary is mocked."""

    socket_calls: list[tuple[Any, ...]] = []
    original_socket = socket.socket

    def _record(*args: Any, **kwargs: Any) -> Any:
        socket_calls.append(args)
        return original_socket(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _record)
    _install_mock_history(monkeypatch)

    fetch_yfinance_regime_adaptive_csvs(
        FetchRequest(
            output_dir=tmp_path / "staging",
            date_from=date(2024, 1, 1),
            date_to=date(2024, 3, 31),
            manual_confirmation=True,
        )
    )

    assert socket_calls == [], (
        f"fetcher unexpectedly opened sockets when boundary is mocked: {socket_calls}"
    )


def test_module_docstring_carries_research_only_disclaimer() -> None:
    import scripts.fetch_yfinance_regime_adaptive_csvs as fetcher_module

    docstring = (fetcher_module.__doc__ or "").lower()
    assert "research-only" in docstring or "research only" in docstring


def test_module_does_not_import_forbidden_broker_or_ai_sdks() -> None:
    """The fetcher must not import broker SDKs, AI/LLM SDKs, or paper-API hosts."""

    forbidden_imports = {
        "alpaca",
        "alpaca_trade_api",
        "anthropic",
        "futu",
        "futu_api",
        "ib_insync",
        "ibapi",
        "langchain",
        "openai",
        "polygon",
        "tiger",
        "tradier",
    }
    forbidden_hosts = (
        "alpaca.markets",
        "api.alpaca.markets",
        "api.tradier.com",
        "paper-api.alpaca.markets",
        "polygon.io",
    )

    source = FETCHER_SOURCE_PATH.read_text(encoding="utf-8")
    lowered = source.lower()
    for token in forbidden_imports:
        assert f"import {token}" not in lowered, f"forbidden import: {token}"
        assert f"from {token}" not in lowered, f"forbidden from-import: {token}"
    for host in forbidden_hosts:
        assert host not in lowered, f"forbidden host reference: {host}"


def test_module_does_not_reference_execution_language() -> None:
    """The fetcher must carry no paper- or live-execution phrasing."""

    forbidden_phrases = (
        "broker fill",
        "executed-order",
        "live execution",
        "paper broker",
        "paper execution",
        "place_order",
        "submit_order",
    )
    lowered = FETCHER_SOURCE_PATH.read_text(encoding="utf-8").lower()
    for phrase in forbidden_phrases:
        assert phrase not in lowered, f"forbidden phrase: {phrase}"


def test_module_does_not_read_os_environ() -> None:
    source = FETCHER_SOURCE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in source, "fetcher must not read os.environ"
    assert "os.getenv" not in source, "fetcher must not read os.getenv"


def test_yfinance_is_the_only_third_party_import() -> None:
    """The fetcher source itself must only depend on yfinance + stdlib."""

    source = FETCHER_SOURCE_PATH.read_text(encoding="utf-8")
    # We only assert on explicit third-party `import X` / `from X` lines that name a
    # well-known forbidden package. The narrower "no requests / no http.client" rule
    # is enforced for strategy modules elsewhere; in scripts/ we permit yfinance to
    # bring its own transitive deps.
    forbidden = ("import requests", "from requests", "import http.client", "from http.client")
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered, f"fetcher must not import {token}"
    assert "import yfinance" in source, "fetcher must import yfinance (authorized entry)"

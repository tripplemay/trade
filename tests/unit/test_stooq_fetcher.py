"""Unit tests for the opt-in Stooq fetcher helper.

Research-only: every HTTP boundary is mocked so the test suite never opens a real
socket and never reaches the public Stooq endpoint.
"""

from __future__ import annotations

import csv
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

from scripts.fetch_stooq_regime_adaptive_csvs import (
    COVERAGE_THRESHOLD,
    DEFAULT_ALLOW_SHORT_HISTORY,
    EXPECTED_STOOQ_HEADER,
    MANUAL_CONFIRM_FLAG,
    OUTPUT_CSV_HEADER,
    SHORT_HISTORY_INCEPTIONS,
    STOOQ_BASE_URL,
    STOOQ_HOST,
    FetchRequest,
    StooqFetcherError,
    _build_stooq_url,
    _expected_business_days,
    _http_get,
    build_arg_parser,
    fetch_stooq_regime_adaptive_csvs,
    main,
)
from trade.strategies.regime_adaptive.snapshot import REQUIRED_TICKERS

FETCHER_MODULE = "scripts.fetch_stooq_regime_adaptive_csvs"
FETCHER_SOURCE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "fetch_stooq_regime_adaptive_csvs.py"
)


@dataclass
class _FakeResponse:
    status: int
    body: bytes

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def _build_stooq_body(
    date_from: date, date_to: date, *, start_price: float = 100.0
) -> bytes:
    rows: list[str] = [",".join(EXPECTED_STOOQ_HEADER)]
    current = date_from
    price = start_price
    while current <= date_to:
        if current.weekday() < 5:
            open_value = price
            high_value = price + 0.5
            low_value = price - 0.5
            close_value = price + 0.1
            volume_value = 1_000_000
            rows.append(
                f"{current.isoformat()},{open_value:.4f},{high_value:.4f},"
                f"{low_value:.4f},{close_value:.4f},{volume_value}"
            )
            price += 0.05
        current += timedelta(days=1)
    return ("\n".join(rows) + "\n").encode("utf-8")


def _ticker_from_url(url: str) -> str:
    params = parse_qs(urlparse(url).query)
    raw = params["s"][0]
    return raw.split(".")[0].upper()


def _window_from_url(url: str) -> tuple[date, date]:
    params = parse_qs(urlparse(url).query)
    d1 = params["d1"][0]
    d2 = params["d2"][0]
    return (
        date(int(d1[0:4]), int(d1[4:6]), int(d1[6:8])),
        date(int(d2[0:4]), int(d2[4:6]), int(d2[6:8])),
    )


def _full_universe_bodies(
    date_from: date, date_to: date, *, sgov_inception: date | None = None
) -> dict[str, Callable[[date, date], bytes]]:
    """Return a per-ticker payload builder respecting SGOV inception when given."""

    def builder(ticker: str) -> Callable[[date, date], bytes]:
        def _build(window_from: date, window_to: date) -> bytes:
            effective_from = window_from
            if (
                ticker == "SGOV"
                and sgov_inception is not None
                and effective_from < sgov_inception
            ):
                effective_from = sgov_inception
            return _build_stooq_body(effective_from, window_to)

        return _build

    return {ticker: builder(ticker) for ticker in REQUIRED_TICKERS}


def _install_mock_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payloads: dict[str, Callable[[date, date], bytes]] | None = None,
    raise_for: dict[str, BaseException] | None = None,
    status: int = 200,
    calls: list[str] | None = None,
) -> None:
    raise_for = raise_for or {}

    def _fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.get_full_url() if hasattr(request, "get_full_url") else str(request)
        if calls is not None:
            calls.append(url)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != STOOQ_HOST:
            raise AssertionError(f"unexpected outbound URL in mock: {url}")
        ticker = _ticker_from_url(url)
        if ticker in raise_for:
            raise raise_for[ticker]
        window_from, window_to = _window_from_url(url)
        builder = (payloads or {}).get(ticker)
        if builder is None:
            body = _build_stooq_body(window_from, window_to)
        else:
            body = builder(window_from, window_to)
        return _FakeResponse(status=status, body=body)

    monkeypatch.setattr(f"{FETCHER_MODULE}.urlopen", _fake_urlopen)


def _block_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network access is not allowed in stooq fetcher tests")

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


def test_build_stooq_url_uses_lowercase_us_suffix_and_compact_dates() -> None:
    url = _build_stooq_url("SPY", date(2018, 1, 1), date(2025, 12, 31))
    assert url == f"{STOOQ_BASE_URL}?s=spy.us&i=d&d1=20180101&d2=20251231"


def test_happy_path_writes_nine_uppercase_csvs_with_canonical_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    payloads = _full_universe_bodies(
        date(2018, 1, 1), date(2025, 12, 31), sgov_inception=date(2020, 5, 28)
    )
    calls: list[str] = []
    _install_mock_urlopen(monkeypatch, payloads=payloads, calls=calls)

    summary = fetch_stooq_regime_adaptive_csvs(
        FetchRequest(
            output_dir=tmp_path / "staging",
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    assert len(calls) == len(REQUIRED_TICKERS), "expected one HTTP call per ticker"
    assert {result.ticker for result in summary.results} == set(REQUIRED_TICKERS)
    for result in summary.results:
        assert result.http_status == 200
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
    with pytest.raises(StooqFetcherError, match="manual confirmation"):
        fetch_stooq_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=False,
            )
        )


def test_http_error_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    payloads = _full_universe_bodies(
        date(2018, 1, 1), date(2025, 12, 31), sgov_inception=date(2020, 5, 28)
    )
    _install_mock_urlopen(
        monkeypatch,
        payloads=payloads,
        raise_for={
            "SPY": HTTPError(
                url="https://stooq.com/q/d/l/?s=spy.us",
                code=503,
                msg="Service Unavailable",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,
            )
        },
    )

    with pytest.raises(StooqFetcherError, match="HTTP 503"):
        fetch_stooq_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_url_error_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    payloads = _full_universe_bodies(
        date(2018, 1, 1), date(2025, 12, 31), sgov_inception=date(2020, 5, 28)
    )
    _install_mock_urlopen(
        monkeypatch,
        payloads=payloads,
        raise_for={"QQQ": URLError("temporary DNS failure")},
    )

    with pytest.raises(StooqFetcherError, match="network error"):
        fetch_stooq_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_malformed_csv_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    payloads: dict[str, Callable[[date, date], bytes]] = {
        ticker: (lambda _from, _to: _build_stooq_body(_from, _to))
        for ticker in REQUIRED_TICKERS
    }
    payloads["VEA"] = lambda _from, _to: b"<!doctype html><html>Maintenance</html>"
    _install_mock_urlopen(monkeypatch, payloads=payloads)

    with pytest.raises(StooqFetcherError, match="unexpected Stooq header"):
        fetch_stooq_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_no_data_response_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    payloads: dict[str, Callable[[date, date], bytes]] = {
        ticker: (lambda _from, _to: _build_stooq_body(_from, _to))
        for ticker in REQUIRED_TICKERS
    }
    payloads["GLD"] = lambda _from, _to: b"No data\n"
    _install_mock_urlopen(monkeypatch, payloads=payloads)

    with pytest.raises(StooqFetcherError, match="No data"):
        fetch_stooq_regime_adaptive_csvs(
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
    payloads: dict[str, Callable[[date, date], bytes]] = {
        ticker: (lambda _from, _to: _build_stooq_body(_from, _to))
        for ticker in REQUIRED_TICKERS
    }
    # Return only the last six months for SPY — clearly below the 95% gate.
    payloads["SPY"] = lambda _from, _to: _build_stooq_body(
        date(2025, 7, 1), _to
    )
    _install_mock_urlopen(monkeypatch, payloads=payloads)

    with pytest.raises(StooqFetcherError, match="insufficient coverage for SPY"):
        fetch_stooq_regime_adaptive_csvs(
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
    payloads = _full_universe_bodies(
        date(2018, 1, 1), date(2025, 12, 31), sgov_inception=date(2020, 5, 28)
    )
    calls: list[str] = []
    _install_mock_urlopen(monkeypatch, payloads=payloads, calls=calls)

    summary = fetch_stooq_regime_adaptive_csvs(
        FetchRequest(
            output_dir=tmp_path / "staging",
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    sgov_calls = [url for url in calls if "s=sgov.us" in url]
    assert len(sgov_calls) == 1
    assert "d1=20200528" in sgov_calls[0]
    sgov_result = next(r for r in summary.results if r.ticker == "SGOV")
    assert sgov_result.short_history_exempt is True
    assert sgov_result.first_date == date(2020, 5, 28)


def test_sgov_short_history_rejected_when_allowance_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_socket(monkeypatch)
    payloads = _full_universe_bodies(
        date(2018, 1, 1), date(2025, 12, 31), sgov_inception=date(2020, 5, 28)
    )
    _install_mock_urlopen(monkeypatch, payloads=payloads)

    with pytest.raises(StooqFetcherError, match="insufficient coverage for SGOV"):
        fetch_stooq_regime_adaptive_csvs(
            FetchRequest(
                output_dir=tmp_path / "staging",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
                allow_short_history=frozenset(),
            )
        )


def test_http_get_refuses_non_stooq_url() -> None:
    with pytest.raises(StooqFetcherError, match="only https://stooq.com"):
        _http_get(
            url="https://api.alpaca.markets/v2/clock",
            timeout_seconds=5,
            user_agent="x",
        )


def test_http_get_refuses_plain_http_scheme() -> None:
    with pytest.raises(StooqFetcherError, match="only https://stooq.com"):
        _http_get(
            url="http://stooq.com/q/d/l/?s=spy.us",
            timeout_seconds=5,
            user_agent="x",
        )


def test_expected_business_days_counts_weekdays_only() -> None:
    # 2024-01-01 (Mon) through 2024-01-14 (Sun) → 10 weekdays.
    assert _expected_business_days(date(2024, 1, 1), date(2024, 1, 14)) == 10


def test_date_to_before_date_from_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(StooqFetcherError, match="precedes date_from"):
        fetch_stooq_regime_adaptive_csvs(
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
    payloads = _full_universe_bodies(
        date(2018, 1, 1), date(2025, 12, 31), sgov_inception=date(2020, 5, 28)
    )
    _install_mock_urlopen(monkeypatch, payloads=payloads)

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
    assert "Stooq fetch summary" in captured.out
    assert "research-only" in captured.out.lower()


def test_cli_main_without_manual_confirmation_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # urlopen should never be reached, but install a tripwire so we can prove it.
    def _trip(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("urlopen must not be called when manual flag is missing")

    monkeypatch.setattr(f"{FETCHER_MODULE}.urlopen", _trip)

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
    payloads = _full_universe_bodies(
        date(2024, 1, 1), date(2024, 3, 31), sgov_inception=date(2020, 5, 28)
    )
    _install_mock_urlopen(monkeypatch, payloads=payloads)

    summary = fetch_stooq_regime_adaptive_csvs(
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
        # date is ISO
        date.fromisoformat(row["date"])
        # numeric fields parse as float
        for key in ("open", "high", "low", "close", "adjusted_close"):
            float(row[key])
        int(row["volume"])
    # Sorted ascending by date
    assert [row["date"] for row in rows] == sorted(row["date"] for row in rows)


def test_no_real_socket_usage_under_default_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fetcher must never open a real socket when its HTTP boundary is mocked."""

    socket_calls: list[tuple[Any, ...]] = []
    original_socket = socket.socket

    def _record(*args: Any, **kwargs: Any) -> Any:
        socket_calls.append(args)
        return original_socket(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _record)
    payloads = _full_universe_bodies(
        date(2024, 1, 1), date(2024, 3, 31), sgov_inception=date(2020, 5, 28)
    )
    _install_mock_urlopen(monkeypatch, payloads=payloads)

    fetch_stooq_regime_adaptive_csvs(
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
    import scripts.fetch_stooq_regime_adaptive_csvs as fetcher_module

    docstring = (fetcher_module.__doc__ or "").lower()
    assert "research-only" in docstring or "research only" in docstring


def test_module_does_not_import_forbidden_broker_or_ai_sdks() -> None:
    """The fetcher module must not import broker SDKs, AI/LLM SDKs, or paper-API hosts."""

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
        "requests",
        "tiger",
        "tradier",
        "yfinance",
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


def _ticker_payloads_for_window(
    payloads: Iterable[str],
) -> dict[str, Callable[[date, date], bytes]]:
    """Helper: identity payload builders for an iterable of tickers (smoke check)."""

    return {ticker: (lambda _from, _to: _build_stooq_body(_from, _to)) for ticker in payloads}

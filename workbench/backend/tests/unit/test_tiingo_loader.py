"""B027 F001 — TiingoSnapshotLoader behaviour.

The tests inject a fake ``httpx.Client`` so the entire suite stays
offline (CI requirement) and so each adversarial scenario — auth
failure, 5xx storm, rate-limit reply, malformed payload — can be
asserted deterministically. Real Tiingo HTTP traffic is verified
once at L2 by the evaluator (B027 F003 spec acceptance).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from workbench_api.data.cost_guard import BudgetExceeded, MonthlyBudgetGuard
from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data.tiingo_loader import (
    TIINGO_BASE_URL,
    TiingoSnapshotLoader,
)


class _NoopGuard:
    """Stand-in for :class:`MonthlyBudgetGuard` that counts calls but
    never raises or touches the DB. Lets the network-layer tests focus
    on retry / parse behaviour without standing up the budget-log
    fixture for every spec."""

    def __init__(self) -> None:
        self.calls = 0

    def check_and_increment(self) -> None:
        self.calls += 1


class _StubResponse:
    """Minimal stand-in for ``httpx.Response`` that supports the surface the
    loader actually touches (``status_code`` + ``json`` + ``raise_for_status``
    + ``request``). Using a hand-rolled stub keeps the test suite agnostic
    to which httpx minor version is installed."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("GET", "https://api.tiingo.com/fake")

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"stub {self.status_code}",
                request=self.request,
                response=self,  # type: ignore[arg-type]
            )


class _StubClient:
    """Stand-in for ``httpx.Client`` driving the loader through a scripted
    sequence of responses or raised network errors."""

    def __init__(
        self,
        responses: list[_StubResponse | Exception] | None = None,
    ) -> None:
        self._responses: list[_StubResponse | Exception] = list(responses or [])
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, params: dict[str, str]) -> _StubResponse:
        self.calls.append((url, dict(params)))
        if not self._responses:
            raise AssertionError(f"StubClient ran out of scripted responses for {url}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _ok_bar(bar_date: str = "2026-05-22") -> dict[str, Any]:
    return {
        "date": f"{bar_date}T00:00:00.000Z",
        "open": 520.10,
        "high": 522.50,
        "low": 519.80,
        "close": 521.30,
        "adjClose": 521.30,
        "volume": 42_000_000,
    }


def test_missing_api_key_raises_with_rotation_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructor must fail loudly with a fix pointer when the env
    var is missing — the production callers cannot silently fall back."""

    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        TiingoSnapshotLoader()
    message = str(exc_info.value)
    assert "TIINGO_API_KEY" in message
    assert "GitHub repo secret" in message


def test_api_key_resolves_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the explicit kwarg is omitted, the env var feeds the key."""

    monkeypatch.setenv("TIINGO_API_KEY", "env-key-xyz")
    loader = TiingoSnapshotLoader(
        client=_StubClient(), sleep=lambda _s: None, guard=_NoopGuard()
    )
    assert loader.api_key == "env-key-xyz"


def test_fetch_daily_bars_parses_tiingo_payload() -> None:
    """Happy-path parse mirrors Tiingo's daily-prices schema field-by-field."""

    client = _StubClient([_StubResponse(200, [_ok_bar("2026-05-22"), _ok_bar("2026-05-23")])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    bars = loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 23))
    assert len(bars) == 2
    first = bars[0]
    assert isinstance(first, PriceBar)
    assert first.ticker == "SPY"
    assert first.bar_date == date(2026, 5, 22)
    assert first.adj_close == 521.30
    assert first.volume == 42_000_000
    url, params = client.calls[0]
    assert url == f"{TIINGO_BASE_URL}/daily/spy/prices"
    assert params["startDate"] == "2026-05-22"
    assert params["format"] == "json"


def test_fetch_daily_bars_retries_on_5xx_then_succeeds() -> None:
    """3-attempt retry policy: two 503s then a 200 → caller sees success."""

    client = _StubClient(
        [
            _StubResponse(503, {"detail": "transient"}),
            _StubResponse(502, {"detail": "transient"}),
            _StubResponse(200, [_ok_bar()]),
        ]
    )
    sleeps: list[float] = []
    loader = TiingoSnapshotLoader(
        api_key="k",
        client=client,
        sleep=lambda s: sleeps.append(s),
        guard=_NoopGuard(),
    )
    bars = loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))
    assert len(bars) == 1
    # Backoff sleeps must grow exponentially across the 2 failed attempts.
    assert sleeps == [0.5, 1.0]


def test_fetch_daily_bars_retries_on_429_rate_limit() -> None:
    """Tiingo returning 429 must trigger the same backoff path as 5xx."""

    client = _StubClient(
        [
            _StubResponse(429, {"detail": "rate limit"}),
            _StubResponse(200, [_ok_bar()]),
        ]
    )
    sleeps: list[float] = []
    loader = TiingoSnapshotLoader(
        api_key="k",
        client=client,
        sleep=lambda s: sleeps.append(s),
        guard=_NoopGuard(),
    )
    bars = loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))
    assert len(bars) == 1
    assert sleeps == [0.5]


def test_fetch_daily_bars_exhausts_retries_and_raises() -> None:
    """After MAX_RETRIES sustained 5xx, the last error propagates so the
    caller can decide whether to alert + skip the ticker for this run."""

    client = _StubClient(
        [
            _StubResponse(500, {"detail": "boom"}),
            _StubResponse(500, {"detail": "boom"}),
            _StubResponse(500, {"detail": "boom"}),
        ]
    )
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    with pytest.raises(httpx.HTTPStatusError):
        loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))


def test_fetch_daily_bars_clamps_future_to_date() -> None:
    """PIT correctness: a to_date in the future must be clamped to today
    before being sent on the wire, otherwise the request would
    semantically ask for unobservable data."""

    client = _StubClient([_StubResponse(200, [_ok_bar()])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    future = date.today() + timedelta(days=10)
    loader.fetch_daily_bars("SPY", date.today() - timedelta(days=1), future)
    _url, params = client.calls[0]
    assert params["endDate"] == date.today().isoformat()


def test_fetch_daily_bars_raises_on_missing_field() -> None:
    """Tiingo schema drift surfaces as a ValueError with the offending
    ticker + payload key set so the ingest job can fail loudly rather
    than silently writing PriceBars with zero adj_close."""

    bad = {**_ok_bar(), "adjClose": None}
    del bad["adjClose"]
    client = _StubClient([_StubResponse(200, [bad])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    with pytest.raises(ValueError) as exc_info:
        loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))
    assert "adjClose" in str(exc_info.value)
    assert "SPY" in str(exc_info.value)


def test_fetch_daily_bars_raises_when_payload_not_a_list() -> None:
    """A non-list top-level payload (Tiingo error dict, HTML 502 page) is
    a schema violation and must not be parsed into PriceBars."""

    client = _StubClient([_StubResponse(200, {"detail": "Bad ticker"})])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    with pytest.raises(ValueError) as exc_info:
        loader.fetch_daily_bars("BAD", date(2026, 5, 22), date(2026, 5, 22))
    assert "non-list" in str(exc_info.value)


def test_fetch_daily_bars_retries_on_network_error() -> None:
    """A connection-layer error (DNS, TLS, socket) is treated like a 5xx
    — the backoff loop gets a chance before the run is given up."""

    client = _StubClient(
        [
            httpx.ConnectError("temporary dns failure"),
            _StubResponse(200, [_ok_bar()]),
        ]
    )
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    bars = loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))
    assert len(bars) == 1


def test_health_check_returns_true_on_200() -> None:
    """A 200 from the daily-prices smoke endpoint signals the key works."""

    client = _StubClient([_StubResponse(200, [_ok_bar()])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    assert loader.health_check() is True


def test_health_check_returns_false_on_auth_failure() -> None:
    """A 401 must surface as ``health_check() -> False`` so the caller
    can distinguish "key invalid" from "vendor unreachable"."""

    client = _StubClient([_StubResponse(401, {"detail": "Not authorized"})])
    loader = TiingoSnapshotLoader(
        api_key="bad", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    assert loader.health_check() is False


def test_multi_ticker_sequential_fetch_uses_one_request_per_ticker() -> None:
    """Stays inside Tiingo's 60 req/hour budget by issuing one daily-
    prices request per ticker (no implicit fan-out / batching). The
    caller controls the sequence + rate, this test just pins the
    1:1 request-to-ticker shape."""

    client = _StubClient(
        [
            _StubResponse(200, [_ok_bar("2026-05-22")]),
            _StubResponse(200, [_ok_bar("2026-05-22")]),
            _StubResponse(200, [_ok_bar("2026-05-22")]),
        ]
    )
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_NoopGuard()
    )
    for ticker in ("SPY", "QQQ", "IEF"):
        loader.fetch_daily_bars(ticker, date(2026, 5, 22), date(2026, 5, 22))
    assert len(client.calls) == 3
    assert {call[0] for call in client.calls} == {
        f"{TIINGO_BASE_URL}/daily/spy/prices",
        f"{TIINGO_BASE_URL}/daily/qqq/prices",
        f"{TIINGO_BASE_URL}/daily/ief/prices",
    }


# --- F002: cost guard integration ----------------------------------------


def test_fetch_daily_bars_calls_guard_before_http() -> None:
    """The guard must be invoked exactly once per fetch_daily_bars call,
    before the HTTP layer sees anything. Order matters so a tripped
    cap halts the call before paying network time."""

    guard = _NoopGuard()
    client = _StubClient([_StubResponse(200, [_ok_bar()])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=guard
    )
    loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))
    assert guard.calls == 1


def test_fetch_daily_bars_skips_http_when_guard_raises_budget_exceeded() -> None:
    """A BudgetExceeded raise must propagate out of fetch_daily_bars and
    the HTTP client must remain untouched — the whole point of the cap
    is to stop the network call BEFORE it happens."""

    class _ExceededGuard:
        def check_and_increment(self) -> None:
            raise BudgetExceeded("cap reached in test")

    client = _StubClient([_StubResponse(200, [_ok_bar()])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_ExceededGuard()
    )
    with pytest.raises(BudgetExceeded):
        loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 22))
    assert client.calls == []


def test_health_check_also_passes_through_guard() -> None:
    """B027 F003 fix-round 1: spec L2 §7 verifies ``health_check()`` →
    budget_log +1, so the guard must fire on the probe path too — not
    just on ``fetch_daily_bars``. A tripped cap should raise out of
    health_check just like it does from fetch_daily_bars; an operator
    running ``health_check`` on a budget-exhausted month learns the
    cause immediately instead of seeing a confusing 200 response."""

    guard = _NoopGuard()
    client = _StubClient([_StubResponse(200, [_ok_bar()])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=guard
    )
    assert loader.health_check() is True
    assert guard.calls == 1


def test_health_check_skips_http_when_guard_raises_budget_exceeded() -> None:
    """If the cap is already hit, ``health_check`` propagates
    BudgetExceeded BEFORE issuing the HTTP probe — the cap is meant to
    halt every Tiingo call, not just the bulk ingest path."""

    class _ExceededGuard:
        def check_and_increment(self) -> None:
            raise BudgetExceeded("cap reached in test")

    client = _StubClient([_StubResponse(200, [_ok_bar()])])
    loader = TiingoSnapshotLoader(
        api_key="k", client=client, sleep=lambda _s: None, guard=_ExceededGuard()
    )
    with pytest.raises(BudgetExceeded):
        loader.health_check()
    assert client.calls == []


def test_default_guard_is_monthly_budget_guard_default() -> None:
    """Constructor default must produce a real MonthlyBudgetGuard with
    the spec-pinned cap (so a forgotten ``guard=`` kwarg cannot silently
    disable the safety rail)."""

    loader = TiingoSnapshotLoader(
        api_key="k", client=_StubClient(), sleep=lambda _s: None
    )
    assert isinstance(loader._guard, MonthlyBudgetGuard)
    assert loader._guard.monthly_cap_usd == 10.0

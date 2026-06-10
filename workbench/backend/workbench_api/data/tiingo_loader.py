"""Tiingo Starter daily-OHLCV adapter.

Implements :class:`workbench_api.data.snapshot_loader.SnapshotLoader`
against the Tiingo end-of-day prices endpoint
(``https://api.tiingo.com/tiingo/daily/{ticker}/prices``). B027 lands
only the adapter; cost-guarded usage tracking + budget enforcement
follow in B027 F002 (``cost_guard.py`` + ``budget_log`` repository).

Why httpx and not the official Tiingo Python SDK:

* The strategy-code path stays SDK-free so a future vendor swap is a
  new adapter file, not a refactor of imports across the strategy
  surface. ``requests``/``httpx`` is a thin enough wrapper that any
  successor vendor adapter can mirror this shape.
* Tiingo's ``adjClose`` field is the only field-name quirk this
  loader normalises into ``PriceBar.adj_close``; everything else
  maps 1:1 by name.

PIT correctness is enforced by clamping ``to_date`` to today before
issuing the request — Tiingo silently returns an empty list for
future ranges, but the explicit clamp keeps the log message correct
and lets us assert it in a unit test without hitting the live API.

Retry policy (5xx / 429):

* Up to 3 attempts; exponential backoff capped at 8 seconds.
* 4xx other than 429 fails fast — those are configuration errors
  (wrong ticker, malformed range) where retrying just wastes the
  monthly rate-limit budget.
* Network-level connection errors retry with the same policy.

The ``BudgetExceeded`` integration (cost guard) lands in F002; F001's
``TiingoSnapshotLoader`` does not depend on a budget log.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, date, datetime
from typing import Any, Protocol

import httpx

from workbench_api.data.cost_guard import MonthlyBudgetGuard
from workbench_api.data.snapshot_loader import PriceBar, SnapshotLoader


class _HttpClient(Protocol):
    """Subset of ``httpx.Client`` the loader actually uses.

    Defined as a Protocol so unit tests can inject a hand-rolled stub
    without subclassing the heavy ``httpx.Client`` (which would drag
    its real connection-pool implementation into the test path). The
    production constructor still builds a real ``httpx.Client``.
    """

    def get(self, url: str, params: dict[str, str]) -> Any: ...


class _Guard(Protocol):
    """Subset of :class:`MonthlyBudgetGuard` the loader actually invokes.

    Lets unit tests pass a hand-rolled stub (e.g. ``_NoopGuard`` or
    ``_ExceededGuard``) without inheriting from the frozen dataclass.
    Production callers continue to pass a real ``MonthlyBudgetGuard``.
    """

    def check_and_increment(self) -> None: ...

logger = logging.getLogger(__name__)

TIINGO_BASE_URL = "https://api.tiingo.com/tiingo"
"""Public Tiingo REST base. Pinned here so a vendor URL change is a
one-line edit in the adapter, not a hunt across the codebase."""

DEFAULT_TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3
BACKOFF_BASE_SECONDS: float = 0.5
BACKOFF_CAP_SECONDS: float = 8.0


class TiingoSnapshotLoader(SnapshotLoader):
    """SnapshotLoader backed by Tiingo Starter daily-prices endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: _HttpClient | None = None,
        sleep: Any = time.sleep,
        guard: _Guard | None = None,
    ) -> None:
        """Bind the loader to an API key + HTTP client + budget guard.

        ``api_key`` resolves from the explicit argument first, then
        ``TIINGO_API_KEY`` in the process environment. Missing key
        raises immediately — production callers must surface the
        configuration error before any request shape can be built.

        ``client`` and ``sleep`` are injectable so unit tests can
        bypass the live network and the real ``time.sleep`` (which
        would slow retry tests by ~10s). Production callers use the
        defaults.

        ``guard`` defaults to ``MonthlyBudgetGuard.default()`` (cap=$10
        per spec §4.4). :meth:`fetch_daily_bars` calls
        ``guard.check_and_increment`` before issuing the HTTP request,
        so a runaway loop trips :class:`BudgetExceeded` before billing
        is affected. Unit tests inject a guard whose
        ``check_and_increment`` is monkey-patched, sidestepping the DB.
        """

        resolved_key = api_key or os.environ.get("TIINGO_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "TIINGO_API_KEY missing. Configure the GitHub repo secret "
                "TIINGO_API_KEY (Settings → Secrets and variables → Actions) "
                "so the workbench-deploy workflow can inject it into "
                "/etc/workbench/workbench.env via the EnvironmentFile mechanism, "
                "or set TIINGO_API_KEY in your local shell for `python -m pytest` "
                "runs that exercise the real loader path."
            )
        self._api_key = resolved_key
        self._client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Token {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        self._sleep = sleep
        self._guard = guard or MonthlyBudgetGuard.default()

    @property
    def api_key(self) -> str:
        """Resolved Tiingo API key. Exposed for diagnostics; never log this."""

        return self._api_key

    def fetch_daily_bars(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[PriceBar]:
        # Cost guard runs FIRST so a BudgetExceeded raise bypasses the
        # HTTP call entirely — the cap is meant to halt ingest before
        # network spend, not after.
        self._guard.check_and_increment()
        clamped_to = min(to_date, datetime.now(UTC).date())
        if clamped_to < to_date:
            logger.info(
                "tiingo_to_date_clamped",
                extra={
                    "ticker": ticker,
                    "requested_to_date": to_date.isoformat(),
                    "clamped_to_date": clamped_to.isoformat(),
                },
            )
        payload = self._get_with_retry(
            f"{TIINGO_BASE_URL}/daily/{ticker.lower()}/prices",
            params={
                "startDate": from_date.isoformat(),
                "endDate": clamped_to.isoformat(),
                "format": "json",
            },
        )
        if not isinstance(payload, list):
            raise ValueError(
                f"Tiingo /daily/{ticker}/prices returned non-list payload of "
                f"type {type(payload).__name__}; cannot parse to PriceBar list"
            )
        return [_parse_bar(ticker, entry) for entry in payload]

    def health_check(self) -> bool:
        # B027 F003 fix-round 1: even ``health_check`` issues a live
        # Tiingo HTTP call, so it must count against the same monthly
        # budget the fetch path does. Spec F003 L2 §7 specifically
        # verifies ``health_check() → budget_log +1`` and the original
        # F002 wiring only ran the guard on ``fetch_daily_bars``.
        self._guard.check_and_increment()
        try:
            self._get_with_retry(
                f"{TIINGO_BASE_URL}/daily/spy/prices",
                params={"startDate": datetime.now(UTC).date().isoformat(), "format": "json"},
            )
        except _AuthFailure:
            return False
        return True

    def _get_with_retry(self, url: str, *, params: dict[str, str]) -> Any:
        """Issue GET with bounded retry on 5xx + 429.

        Auth failures (401/403) raise :class:`_AuthFailure` so the
        public surface can distinguish "key invalid" (return False
        from ``health_check``) from "vendor unreachable" (propagates).
        Other 4xx raise ``httpx.HTTPStatusError`` so callers see the
        actual configuration mistake.
        """

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "tiingo_network_retry",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._sleep_for_attempt(attempt)
                continue

            status = response.status_code
            if status == 200:
                return response.json()
            if status in (401, 403):
                raise _AuthFailure(
                    f"Tiingo auth failed ({status}); rotate TIINGO_API_KEY"
                )
            if status == 429 or 500 <= status < 600:
                last_error = httpx.HTTPStatusError(
                    f"Tiingo {status}", request=response.request, response=response
                )
                logger.warning(
                    "tiingo_status_retry",
                    extra={
                        "url": url,
                        "status": status,
                        "attempt": attempt + 1,
                    },
                )
                self._sleep_for_attempt(attempt)
                continue
            response.raise_for_status()
        # All retries exhausted.
        assert last_error is not None  # noqa: S101 — logic-protected branch
        logger.error(
            "tiingo_retries_exhausted",
            extra={"url": url, "attempts": MAX_RETRIES, "error": str(last_error)},
        )
        raise last_error

    def _sleep_for_attempt(self, attempt: int) -> None:
        delay = min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_CAP_SECONDS)
        self._sleep(delay)


class _AuthFailure(RuntimeError):
    """Raised internally when Tiingo returns 401/403.

    Kept private so the public surface is just ``health_check() -> bool``
    + ``fetch_daily_bars`` raising standard ``httpx`` errors. Auth
    failures during ``fetch_daily_bars`` propagate as well — they
    indicate a real misconfiguration the caller must surface.
    """


def _parse_bar(ticker: str, payload: dict[str, Any]) -> PriceBar:
    """Map a Tiingo daily-bar JSON dict into a :class:`PriceBar`.

    Tiingo schema: ``date``, ``open``, ``high``, ``low``, ``close``,
    ``adjClose``, ``volume`` (plus a handful of split/dividend fields
    we do not currently propagate). Missing any of the required keys
    raises ``ValueError`` with the offending payload context so a
    Tiingo schema drift fails loudly during ingest.
    """

    required = ("date", "open", "high", "low", "close", "adjClose", "volume")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(
            f"Tiingo bar for {ticker} missing fields {missing}; "
            f"got keys {sorted(payload.keys())}"
        )
    raw_date = payload["date"]
    # Tiingo returns ISO-8601 with a 'T00:00:00.000Z' tail; truncate to date.
    bar_date_str = str(raw_date).split("T", 1)[0]
    return PriceBar(
        ticker=ticker,
        bar_date=date.fromisoformat(bar_date_str),
        open=float(payload["open"]),
        high=float(payload["high"]),
        low=float(payload["low"]),
        close=float(payload["close"]),
        adj_close=float(payload["adjClose"]),
        volume=int(payload["volume"]),
    )

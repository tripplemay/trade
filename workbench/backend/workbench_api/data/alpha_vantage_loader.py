"""B035 F001 — Alpha Vantage market-context adapter.

Fetches latest quotes from Alpha Vantage's free ``GLOBAL_QUOTE`` endpoint
(``https://www.alphavantage.co/query``) for the B035 index series — SPY /
QQQ / UUP — writes the raw response to the snapshot foundation, and
persists the latest observation idempotently.

``GLOBAL_QUOTE`` returns a single latest quote per request, so the daily
3-series fetch costs **3 requests/day** — comfortably under Alpha
Vantage's free-tier **25 req/day** cap (spec §9). The per-request
:class:`RateLimitGuard` hook is the enforcement seam should that ever
need tightening; the default is a no-op.

DXY note: Alpha Vantage's free ``GLOBAL_QUOTE`` covers US-listed
equities/ETFs, not the ICE DXY index, so the dollar series uses **UUP**
(Invesco DB US Dollar Index Bullish ETF) as the standard DXY-tracking
proxy (spec §2 #5 allows an equivalent ETF). The series_id stored is the
actual symbol fetched (``UUP``); the F003 card labels it as the dollar
proxy.

Mirrors the Tiingo / FRED adapter shape (httpx Protocol, bounded retry).
Alpha Vantage signals throttling / bad symbols via a ``Note`` /
``Information`` / ``Error Message`` field instead of an HTTP error, so
those are detected and raised explicitly.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, date, datetime
from typing import Any, Protocol

import httpx

from workbench_api.data.market_context_common import (
    SOURCE_ALPHA_VANTAGE,
    NoOpRateLimitGuard,
    ObservationPoint,
    RateLimitGuard,
)
from workbench_api.db.repositories.market_context import MarketContextRepository
from workbench_api.news.snapshot import NewsSnapshotWriter

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co"
"""Public Alpha Vantage REST base. Pinned for one-line vendor swaps."""

ALPHA_VANTAGE_SERIES: tuple[str, ...] = ("SPY", "QQQ", "UUP")
"""B035 index series via GLOBAL_QUOTE: S&P 500 / Nasdaq-100 / US Dollar
(UUP, the DXY-tracking ETF — DXY itself is not on the free tier)."""

DEFAULT_TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3
BACKOFF_BASE_SECONDS: float = 0.5
BACKOFF_CAP_SECONDS: float = 8.0


class _HttpClient(Protocol):
    def get(self, url: str, params: dict[str, str]) -> Any: ...


class AlphaVantageLoader:
    """Adapter for the Alpha Vantage ``GLOBAL_QUOTE`` endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: _HttpClient | None = None,
        sleep: Any = time.sleep,
        guard: RateLimitGuard | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "ALPHAVANTAGE_API_KEY missing. Configure the GitHub repo "
                "secret ALPHAVANTAGE_API_KEY (Settings → Secrets and variables "
                "→ Actions) so the bootstrap-env workflow can inject it into "
                "/etc/workbench/workbench.env via the systemd EnvironmentFile "
                "mechanism, or set ALPHAVANTAGE_API_KEY in your local shell for "
                "`python -m pytest` runs that exercise the real loader path. "
                "Get a free key at https://www.alphavantage.co/support/#api-key."
            )
        self._api_key = resolved_key
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
        self._sleep = sleep
        self._guard: RateLimitGuard = guard or NoOpRateLimitGuard()

    @property
    def api_key(self) -> str:
        """Resolved Alpha Vantage API key. Exposed for diagnostics; never log."""

        return self._api_key

    def fetch_series(
        self, symbol: str
    ) -> tuple[dict[str, Any], list[ObservationPoint]]:
        """Fetch + parse the latest quote for ``symbol``. Returns
        ``(raw_payload, [latest_point])``."""

        self._guard.check_and_increment()
        payload = self._get_with_retry(
            f"{ALPHA_VANTAGE_BASE_URL}/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self._api_key,
            },
        )
        return payload, _parse_global_quote(symbol, payload)

    def fetch_and_store(
        self,
        symbol: str,
        *,
        repo: MarketContextRepository,
        writer: NewsSnapshotWriter,
        snapshot_date: date | None = None,
    ) -> int:
        """Fetch one symbol's latest quote, snapshot the raw response,
        persist the observation idempotently. Returns count newly saved."""

        payload, points = self.fetch_series(symbol)
        snap = writer.write(
            source=SOURCE_ALPHA_VANTAGE,
            published_on=snapshot_date or datetime.now(UTC).date(),
            identifier=symbol,
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            ext="json",
        )
        saved = 0
        for point in points:
            if repo.save_if_new(
                series_id=symbol,
                source=SOURCE_ALPHA_VANTAGE,
                obs_date=point.obs_date,
                value=point.value,
                snapshot_path=snap.relative_path,
            ) is not None:
                saved += 1
        return saved

    def _get_with_retry(self, url: str, *, params: dict[str, str]) -> Any:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "alpha_vantage_network_retry",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._sleep_for_attempt(attempt)
                continue
            status = response.status_code
            if status == 200:
                return response.json()
            if status == 429 or 500 <= status < 600:
                last_error = httpx.HTTPStatusError(
                    f"Alpha Vantage {status}",
                    request=response.request,
                    response=response,
                )
                logger.warning(
                    "alpha_vantage_status_retry",
                    extra={"url": url, "status": status, "attempt": attempt + 1},
                )
                self._sleep_for_attempt(attempt)
                continue
            response.raise_for_status()
        assert last_error is not None  # noqa: S101 — logic-protected branch
        raise last_error

    def _sleep_for_attempt(self, attempt: int) -> None:
        delay = min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_CAP_SECONDS)
        self._sleep(delay)


def _parse_global_quote(symbol: str, payload: Any) -> list[ObservationPoint]:
    """Parse the Alpha Vantage ``GLOBAL_QUOTE`` envelope.

    Envelope (verified against the Alpha Vantage docs; live-validated in
    ``tests/unit/test_alpha_vantage_loader.py``)::

        {"Global Quote": {"01. symbol": "SPY", "05. price": "580.50",
                          "07. latest trading day": "2026-06-03", ...}}

    Alpha Vantage reports throttling / bad symbols via a ``Note`` /
    ``Information`` / ``Error Message`` field (still HTTP 200), so those
    are surfaced as ``ValueError`` rather than silently parsed as empty.
    """

    if not isinstance(payload, dict):
        raise ValueError(
            f"Alpha Vantage {symbol} returned non-dict payload of type "
            f"{type(payload).__name__}"
        )
    for soft_error_key in ("Note", "Information", "Error Message"):
        if soft_error_key in payload:
            raise ValueError(
                f"Alpha Vantage {symbol} returned '{soft_error_key}': "
                f"{payload[soft_error_key]!r} (rate limit or bad symbol)"
            )
    quote = payload.get("Global Quote")
    if not isinstance(quote, dict) or not quote:
        raise ValueError(
            f"Alpha Vantage {symbol} payload missing non-empty 'Global Quote'; "
            f"got keys {sorted(payload.keys())}"
        )
    price = quote.get("05. price")
    trading_day = quote.get("07. latest trading day")
    if price is None or trading_day is None:
        raise ValueError(
            f"Alpha Vantage {symbol} 'Global Quote' missing price / trading "
            f"day; got keys {sorted(quote.keys())}"
        )
    return [
        ObservationPoint(
            obs_date=date.fromisoformat(str(trading_day)),
            value=float(price),
        )
    ]

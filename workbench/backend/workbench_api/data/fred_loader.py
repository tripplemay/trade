"""B035 F001 — FRED market-context adapter.

Fetches FRED (Federal Reserve Economic Data) series observations
(``https://api.stlouisfed.org/fred/series/observations``) for the B035
macro series — 10-year Treasury ``DGS10`` / VIX ``VIXCLS`` / CPI
``CPIAUCSL`` — writes the raw response to the snapshot foundation, and
persists the recent observations idempotently via
:class:`~workbench_api.db.repositories.market_context.MarketContextRepository`.

Mirrors the Tiingo adapter (B027) shape: a thin ``httpx`` wrapper (no
vendor SDK), an injectable ``_HttpClient`` Protocol + ``sleep`` for
offline tests, bounded retry on 5xx/429, and fail-fast on other 4xx.
``FRED_API_KEY`` resolves from the constructor arg then the environment;
missing key raises immediately (§12.9 secret wiring).

The fetch is bounded to the most recent ``limit`` observations
(``sort_order=desc``) — the daily timer only needs the latest context,
and FRED series carry decades of history. FRED encodes a missing data
point as the string ``"."``; those are skipped rather than stored as a
bogus value.
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
    SOURCE_FRED,
    NoOpRateLimitGuard,
    ObservationPoint,
    RateLimitGuard,
)
from workbench_api.db.repositories.market_context import MarketContextRepository
from workbench_api.news.snapshot import NewsSnapshotWriter

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"
"""Public FRED REST base. Pinned here so a vendor URL change is a
one-line edit, not a hunt across the codebase."""

FRED_SERIES: tuple[str, ...] = ("DGS10", "VIXCLS", "CPIAUCSL")
"""B035 macro series: 10y Treasury / VIX / CPI (spec §2 #5)."""

DEFAULT_RECENT_LIMIT = 10
DEFAULT_TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3
BACKOFF_BASE_SECONDS: float = 0.5
BACKOFF_CAP_SECONDS: float = 8.0

_MISSING_VALUE = "."


class _HttpClient(Protocol):
    def get(self, url: str, params: dict[str, str]) -> Any: ...


class FREDMarketLoader:
    """Adapter for the FRED ``series/observations`` endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: _HttpClient | None = None,
        sleep: Any = time.sleep,
        guard: RateLimitGuard | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("FRED_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "FRED_API_KEY missing. Configure the GitHub repo secret "
                "FRED_API_KEY (Settings → Secrets and variables → Actions) so "
                "the bootstrap-env workflow can inject it into "
                "/etc/workbench/workbench.env via the systemd EnvironmentFile "
                "mechanism, or set FRED_API_KEY in your local shell for "
                "`python -m pytest` runs that exercise the real loader path. "
                "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html."
            )
        self._api_key = resolved_key
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
        self._sleep = sleep
        self._guard: RateLimitGuard = guard or NoOpRateLimitGuard()

    @property
    def api_key(self) -> str:
        """Resolved FRED API key. Exposed for diagnostics; never log."""

        return self._api_key

    def fetch_series(
        self, series_id: str, *, limit: int = DEFAULT_RECENT_LIMIT
    ) -> tuple[dict[str, Any], list[ObservationPoint]]:
        """Fetch + parse one series. Returns ``(raw_payload, points)``;
        points are the most-recent ``limit`` valid observations."""

        self._guard.check_and_increment()
        payload = self._get_with_retry(
            f"{FRED_BASE_URL}/series/observations",
            params={
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": str(limit),
            },
        )
        return payload, _parse_observations(series_id, payload)

    def fetch_and_store(
        self,
        series_id: str,
        *,
        repo: MarketContextRepository,
        writer: NewsSnapshotWriter,
        snapshot_date: date | None = None,
        limit: int = DEFAULT_RECENT_LIMIT,
    ) -> int:
        """Fetch one series, snapshot the raw response, persist recent
        observations idempotently. Returns the count newly saved."""

        payload, points = self.fetch_series(series_id, limit=limit)
        snap = writer.write(
            source=SOURCE_FRED,
            published_on=snapshot_date or datetime.now(UTC).date(),
            identifier=series_id,
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            ext="json",
        )
        saved = 0
        for point in points:
            if repo.save_if_new(
                series_id=series_id,
                source=SOURCE_FRED,
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
                    "fred_network_retry",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._sleep_for_attempt(attempt)
                continue
            status = response.status_code
            if status == 200:
                return response.json()
            if status == 429 or 500 <= status < 600:
                last_error = httpx.HTTPStatusError(
                    f"FRED {status}", request=response.request, response=response
                )
                logger.warning(
                    "fred_status_retry",
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


def _parse_observations(
    series_id: str, payload: Any
) -> list[ObservationPoint]:
    """Parse the FRED ``observations`` envelope into ``ObservationPoint``s.

    Envelope (per the FRED API docs; the endpoint *path* was
    live-validated 2026-06-04 — a no-key request returns HTTP 400
    "Variable api_key is not set", confirming the path is real, not
    spec-invented. The full success envelope is validated against a real
    key at L2 / once ``FRED_API_KEY`` is configured)::

        {"observations": [{"date": "2026-06-01", "value": "4.25", ...}, ...]}

    Missing points (``value == "."``) are skipped. A malformed envelope
    raises ``ValueError`` so a vendor schema drift fails ingest loudly
    rather than silently writing zero observations.
    """

    if not isinstance(payload, dict) or "observations" not in payload:
        raise ValueError(
            f"FRED series {series_id} payload missing 'observations'; got "
            f"{type(payload).__name__}"
        )
    observations = payload["observations"]
    if not isinstance(observations, list):
        raise ValueError(
            f"FRED series {series_id} 'observations' must be a list; got "
            f"{type(observations).__name__}"
        )
    points: list[ObservationPoint] = []
    for entry in observations:
        if not isinstance(entry, dict) or "date" not in entry or "value" not in entry:
            raise ValueError(
                f"FRED series {series_id} observation missing date/value: {entry!r}"
            )
        raw_value = str(entry["value"]).strip()
        if raw_value == _MISSING_VALUE or raw_value == "":
            continue
        points.append(
            ObservationPoint(
                obs_date=date.fromisoformat(str(entry["date"]).split("T", 1)[0]),
                value=float(raw_value),
            )
        )
    return points

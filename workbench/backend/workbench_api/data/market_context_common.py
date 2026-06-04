"""B035 F001 — shared bits for the market-context loaders.

The FRED + Alpha Vantage loaders both: fetch a provider response, write
the raw bytes to the snapshot foundation, parse one-or-more numeric
observations, and persist them idempotently. This module holds the small
pieces both share so neither loader imports the other:

* :class:`ObservationPoint` — a parsed ``(obs_date, value)`` data point.
* :class:`RateLimitGuard` Protocol + :class:`NoOpRateLimitGuard` — an
  injectable per-request hook. The free tiers are generous relative to
  the daily 3-series fetch (FRED ~120 req/min; Alpha Vantage **25
  req/day** — the binding one), so the default is a no-op; a future
  daily-budget guard can plug in via the Protocol without touching the
  loaders. Tests inject a counting/raising guard to prove the hook fires
  per request (B035 spec §4.3 — the "25/day" enforcement seam).

Raw snapshots reuse :class:`workbench_api.news.snapshot.NewsSnapshotWriter`
— a generic ``{root}/{source}/{YYYY-MM-DD}/{id}.{ext}`` writer (B033) —
under ``data/snapshots/market-context/`` (B035 spec §4.2: reuse the
B027/B029 snapshot foundation). Snapshot writing is a CLI / loader
**write** path, never the API request path, so a repo-relative default
root is fine (cf. the §12.10 request-path self-containment rule, which
only constrains reads on the request path).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

# Source labels (also the snapshot sub-directory under market-context/).
SOURCE_FRED = "fred"
SOURCE_ALPHA_VANTAGE = "alpha_vantage"


@dataclass(frozen=True, slots=True)
class ObservationPoint:
    """One parsed numeric observation for a series."""

    obs_date: date
    value: float


class RateLimitGuard(Protocol):
    """Per-request rate-limit hook. ``check_and_increment`` is called once
    before each provider HTTP request; an implementation may raise to halt
    a run that would exceed the provider's free-tier quota."""

    def check_and_increment(self) -> None: ...


class NoOpRateLimitGuard:
    """Default guard — does nothing. The daily 3-series fetch is well
    under every free-tier quota, so production needs no enforcement; the
    seam exists so a daily-budget guard can be injected later."""

    def check_and_increment(self) -> None:  # noqa: D401 - trivial
        return None

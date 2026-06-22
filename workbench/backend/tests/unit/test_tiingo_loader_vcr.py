"""B073 F001 — Tiingo loader VCR replay (offline, no key, no network).

Complements ``test_tiingo_loader.py`` (in-process fake client). Here the loader
builds its *real* ``httpx.Client``; pytest-recording replays a committed
cassette so the HTTP path — URL shape, query params, JSON-list response,
``adjClose`` → ``adj_close`` mapping — is exercised end to end without a live
Tiingo key. Re-recording against the real API (see tests/cassettes/README.md)
would surface any vendor schema drift the hand-rolled fake cannot.
"""

from __future__ import annotations

from datetime import date

import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data.tiingo_loader import TiingoSnapshotLoader


class _NoopGuard:
    """Budget guard that never raises or touches the DB (offline isolation)."""

    def check_and_increment(self) -> None:  # noqa: D401 — Protocol method
        return None


@pytest.mark.vcr
def test_tiingo_loader_replays_offline() -> None:
    """Real httpx client + committed cassette → deterministic PriceBars.

    The loader constructs a live ``httpx.Client`` (no ``client=`` injection),
    so vcrpy's transport patch intercepts the GET and serves the recorded
    Tiingo daily-prices response with zero network access.
    """

    loader = TiingoSnapshotLoader(api_key="vcr-test-key", guard=_NoopGuard())

    bars = loader.fetch_daily_bars("SPY", date(2026, 5, 22), date(2026, 5, 23))

    assert [b.ticker for b in bars] == ["SPY", "SPY"]
    first = bars[0]
    assert isinstance(first, PriceBar)
    assert first.bar_date == date(2026, 5, 22)
    assert first.close == 521.30
    # adjClose maps to adj_close; the cassette pins them equal for this window.
    assert first.adj_close == 521.30
    assert first.volume == 42_000_000
    assert bars[1].bar_date == date(2026, 5, 23)
    assert bars[1].close == 522.40

"""B073 F001 — SEC EDGAR loader VCR replay (offline, no network).

Complements ``test_sec_edgar_loader.py`` (in-process fake client). The loader
builds its *real* ``httpx.Client``; pytest-recording replays committed cassettes
for the two live endpoints the loader actually calls:

* ``fetch_raw_companyfacts`` → ``/api/xbrl/companyfacts/CIK{cik}.json`` — the
  cassette carries the **real** SEC shape (``cik`` / ``entityName`` / ``facts``).
  Note the unit-test fixtures elsewhere are *synthesised* (a pre-baked
  ``parsed_ratios`` block the real API never returns); ``parse_companyfacts``
  rejects the raw shape on purpose, so the VCR test exercises the raw-fetch path
  the backfill driver consumes, not the parse path.
* ``health_check`` → ``/submissions/CIK0000320193.json`` — a 200 reachability
  probe.

No SEC contact-email env var or network is required: the email is passed
explicitly and ``ticker_cik_map`` is injected so AAPL resolves to CIK 320193
deterministically.
"""

from __future__ import annotations

from typing import Any

import pytest

from workbench_api.data.sec_edgar_loader import SECEDGARFundamentalsLoader

_CONTACT = "research-only@example.com"
_AAPL_CIK_MAP: dict[str, int | None] = {"AAPL": 320193}


class _NoopLimiter:
    """Rate limiter that never waits (offline isolation)."""

    def wait(self) -> None:
        return None


def _loader() -> SECEDGARFundamentalsLoader:
    return SECEDGARFundamentalsLoader(
        contact_email=_CONTACT,
        limiter=_NoopLimiter(),
        sleep=lambda _seconds: None,
        ticker_cik_map=_AAPL_CIK_MAP,
    )


@pytest.mark.vcr
def test_sec_edgar_companyfacts_replays_offline() -> None:
    """Real httpx client + cassette → the raw SEC companyfacts dict."""

    payload: dict[str, Any] = _loader().fetch_raw_companyfacts("AAPL")

    assert payload["cik"] == 320193
    assert payload["entityName"] == "Apple Inc."
    # Real SEC shape: a ``facts.us-gaap`` concept tree, NOT a parsed_ratios block.
    assert "us-gaap" in payload["facts"]
    assert "parsed_ratios" not in payload


@pytest.mark.vcr
def test_sec_edgar_health_check_replays_offline() -> None:
    """Real httpx client + cassette → reachability probe returns True."""

    assert _loader().health_check() is True

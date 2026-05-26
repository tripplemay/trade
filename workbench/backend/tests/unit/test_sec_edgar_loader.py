"""B029 F001 — SECEDGARFundamentalsLoader behaviour.

The tests inject a fake ``httpx.Client`` so the entire suite stays
offline (CI requirement) and so each adversarial scenario — auth
failure / 5xx storm / 429 rate-limit / synthetic-ticker skip — can be
asserted deterministically. Real SEC EDGAR HTTP traffic is verified
once at L2 by the evaluator (B029 F004 spec acceptance).
"""

from __future__ import annotations

import itertools
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from workbench_api.data.fundamentals_loader import FundamentalsRow
from workbench_api.data.sec_edgar_loader import (
    SEC_CONCEPT_NAMES,
    SEC_EDGAR_BASE_URL,
    SECEDGARFundamentalsLoader,
    SimpleRateLimit,
    parse_companyfacts,
)

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1].parent
    / "workbench_api"
    / "data"
    / "fixtures"
    / "sec_edgar_responses"
)


def _load_fixture(name: str) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return parsed


class _StubResponse:
    """Minimal stand-in for ``httpx.Response``."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("GET", "https://data.sec.gov/fake")

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
    """Stand-in for ``httpx.Client`` with scripted responses / errors."""

    def __init__(
        self, responses: list[_StubResponse | Exception] | None = None
    ) -> None:
        self._responses: list[_StubResponse | Exception] = list(responses or [])
        self.calls: list[str] = []

    def get(self, url: str) -> _StubResponse:
        self.calls.append(url)
        if not self._responses:
            raise AssertionError(f"StubClient ran out of scripted responses for {url}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class _NoopLimiter:
    """No-op rate limiter for tests that don't exercise the 10/sec cap."""

    def __init__(self) -> None:
        self.calls = 0

    def wait(self) -> None:
        self.calls += 1


def test_missing_contact_email_raises_with_fix_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructor must fail loudly with a fix pointer when the
    env var is missing — SEC EDGAR will ban the IP for 30 days
    without a valid contact email in the User-Agent header
    (永久边界 (h))."""

    monkeypatch.delenv("SEC_EDGAR_CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        SECEDGARFundamentalsLoader()
    msg = str(exc_info.value)
    assert "SEC_EDGAR_CONTACT_EMAIL" in msg
    assert "GitHub repo secret" in msg
    assert "ban IP" in msg


def test_contact_email_resolves_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the explicit kwarg is omitted, the env var feeds the
    contact email — same pattern as TIINGO_API_KEY in
    :class:`TiingoSnapshotLoader`."""

    monkeypatch.setenv("SEC_EDGAR_CONTACT_EMAIL", "team@example.com")
    loader = SECEDGARFundamentalsLoader(
        client=_StubClient(), limiter=_NoopLimiter(), sleep=lambda _s: None
    )
    assert loader.contact_email == "team@example.com"


def test_default_client_user_agent_header_includes_contact_email() -> None:
    """The User-Agent header must include the contact email verbatim
    — SEC fair-access policy rejects requests whose UA doesn't carry
    a contact. The default constructor builds an :class:`httpx.Client`
    with the headers baked in; the test narrows the protocol-typed
    ``_client`` attribute back to the concrete type to inspect them."""

    loader = SECEDGARFundamentalsLoader(contact_email="ua-test@example.com")
    client = loader._client
    assert isinstance(client, httpx.Client), (
        "default constructor must wire a real httpx.Client when no override is passed"
    )
    ua = client.headers["user-agent"]
    assert "ua-test@example.com" in ua
    assert "Workbench Trade research-only" in ua


def test_ticker_cik_map_contains_all_30_b025_universe_tickers() -> None:
    """The bundled ticker_cik_map.json fixture must cover the B025
    us_quality_momentum 30-ticker universe — 27 real CIKs + 3
    synthetic ZQAI/ZQPT/ZQLH mapped to ``None`` (Planner pre-impl
    adjudication 2026-05-26 decision #3)."""

    loader = SECEDGARFundamentalsLoader(
        contact_email="map-test@example.com",
        client=_StubClient(),
        limiter=_NoopLimiter(),
        sleep=lambda _s: None,
    )
    m = loader.ticker_cik_map
    assert len(m) == 30
    # 3 synthetic entries must map to None.
    for synthetic in ("ZQAI", "ZQPT", "ZQLH"):
        assert synthetic in m
        assert m[synthetic] is None, (
            f"Synthetic ticker {synthetic} must map to None per decision #3."
        )
    # 27 real entries must be int CIKs.
    real_count = sum(1 for cik in m.values() if cik is not None)
    assert real_count == 27, (
        f"Expected 27 real CIKs (30 universe minus 3 synthetic), got {real_count}"
    )
    # Spot-check a few well-known CIKs to catch a typo in the fixture.
    assert m["AAPL"] == 320193
    assert m["MSFT"] == 789019
    assert m["NVDA"] == 1045810


def test_fetch_for_synthetic_ticker_raises_value_error_with_skip_pointer() -> None:
    """ZQAI/ZQPT/ZQLH have CIK ``None`` in the fixture; fetching them
    must raise ``ValueError`` with a "skip in backfill driver" pointer
    so the F002 backfill driver can ``catch + log warn + skip``
    without aborting the batch (decision #3 fail-safe)."""

    loader = SECEDGARFundamentalsLoader(
        contact_email="skip-test@example.com",
        client=_StubClient(),
        limiter=_NoopLimiter(),
        sleep=lambda _s: None,
    )
    with pytest.raises(ValueError) as exc_info:
        loader.fetch_quarterly_fundamentals(
            "ZQAI", date(2014, 1, 1), date(2016, 1, 1)
        )
    msg = str(exc_info.value)
    assert "Synthetic ticker" in msg
    assert "ZQAI" in msg
    assert "skip in backfill driver" in msg


def test_fetch_quarterly_fundamentals_parses_aapl_fixture_four_quarters() -> None:
    """End-to-end happy path: a stubbed companyfacts JSON response
    flows through the loader and produces 4 :class:`FundamentalsRow`
    in filing-date order for the 2014Q4-2015Q3 window."""

    payload = _load_fixture("aapl_companyfacts.json")
    limiter = _NoopLimiter()
    loader = SECEDGARFundamentalsLoader(
        contact_email="aapl-test@example.com",
        client=_StubClient(responses=[_StubResponse(200, payload)]),
        limiter=limiter,
        sleep=lambda _s: None,
    )
    rows = loader.fetch_quarterly_fundamentals(
        "AAPL", date(2014, 1, 1), date(2016, 6, 1)
    )
    assert len(rows) == 4
    assert all(isinstance(r, FundamentalsRow) for r in rows)
    fqs = [r.fiscal_quarter for r in rows]
    assert fqs == ["2014Q4", "2015Q1", "2015Q2", "2015Q3"]
    # Spot-check the first row against the fixture authoritative values.
    first = rows[0]
    assert first.ticker == "AAPL"
    assert first.report_date == date(2015, 2, 4)
    assert first.fiscal_quarter_end == date(2014, 12, 31)
    assert first.roe == 0.4469
    assert first.gross_margin == 0.4353
    # Rate limiter was invoked once per fetch.
    assert limiter.calls == 1


def test_fetch_filters_by_report_date_range() -> None:
    """The ``[from_date, to_date]`` filter operates on ``report_date``
    (the SEC filing date), not the fiscal-quarter-end — a quarter
    that was filed after ``to_date`` must not surface even when its
    fiscal_quarter_end falls inside the window."""

    payload = _load_fixture("aapl_companyfacts.json")
    loader = SECEDGARFundamentalsLoader(
        contact_email="filter-test@example.com",
        client=_StubClient(responses=[_StubResponse(200, payload)]),
        limiter=_NoopLimiter(),
        sleep=lambda _s: None,
    )
    # Window stops before 2015-05-05 → only 2014Q4 surfaces.
    rows = loader.fetch_quarterly_fundamentals(
        "AAPL", date(2014, 1, 1), date(2015, 5, 1)
    )
    assert len(rows) == 1
    assert rows[0].fiscal_quarter == "2014Q4"
    assert rows[0].report_date == date(2015, 2, 4)


def test_fetch_retries_on_5xx_then_succeeds() -> None:
    """SEC EDGAR occasionally returns 5xx; the loader retries up to
    3 attempts with bounded exponential backoff."""

    payload = _load_fixture("aapl_companyfacts.json")
    sleeps: list[float] = []
    stub = _StubClient(
        responses=[
            _StubResponse(503, None),
            _StubResponse(502, None),
            _StubResponse(200, payload),
        ]
    )
    loader = SECEDGARFundamentalsLoader(
        contact_email="retry-test@example.com",
        client=stub,
        limiter=_NoopLimiter(),
        sleep=sleeps.append,
    )
    rows = loader.fetch_quarterly_fundamentals(
        "AAPL", date(2014, 1, 1), date(2016, 6, 1)
    )
    assert len(rows) == 4
    assert len(stub.calls) == 3
    # Two backoff sleeps before the successful third attempt.
    assert len(sleeps) == 2
    assert sleeps == [0.5, 1.0]


def test_fetch_retries_on_429_rate_limit_response() -> None:
    """SEC EDGAR sends 429 when the per-IP burst limit is hit; the
    loader retries that status the same way it retries 5xx (the
    ``SimpleRateLimit`` in-process limiter is a best-effort guard
    not a guarantee — the server's own counter is authoritative)."""

    payload = _load_fixture("nvda_companyfacts.json")
    stub = _StubClient(
        responses=[_StubResponse(429, None), _StubResponse(200, payload)]
    )
    loader = SECEDGARFundamentalsLoader(
        contact_email="429-test@example.com",
        client=stub,
        limiter=_NoopLimiter(),
        sleep=lambda _s: None,
    )
    rows = loader.fetch_quarterly_fundamentals(
        "NVDA", date(2014, 1, 1), date(2016, 6, 1)
    )
    assert len(rows) == 4
    assert len(stub.calls) == 2


def test_health_check_returns_false_on_403_user_agent_rejection() -> None:
    """SEC EDGAR returns 403 when the User-Agent header is missing or
    on a banned IP. The loader must absorb this into
    ``health_check() is False`` so the caller can branch on
    availability without parsing exception types."""

    stub = _StubClient(
        responses=[
            _StubResponse(403, None),
            _StubResponse(403, None),
            _StubResponse(403, None),
        ]
    )
    loader = SECEDGARFundamentalsLoader(
        contact_email="health-test@example.com",
        client=stub,
        limiter=_NoopLimiter(),
        sleep=lambda _s: None,
    )
    assert loader.health_check() is False


def test_health_check_returns_true_on_200_aapl_submissions_probe() -> None:
    """Happy path: SEC accepts the UA header and returns 200 on the
    AAPL submissions probe → ``health_check`` is True."""

    stub = _StubClient(responses=[_StubResponse(200, {"cik": 320193})])
    loader = SECEDGARFundamentalsLoader(
        contact_email="health-ok@example.com",
        client=stub,
        limiter=_NoopLimiter(),
        sleep=lambda _s: None,
    )
    assert loader.health_check() is True
    # The probe must hit the AAPL submissions endpoint.
    assert stub.calls == [f"{SEC_EDGAR_BASE_URL}/submissions/CIK0000320193.json"]


def test_simple_rate_limit_throttles_to_max_calls_per_period() -> None:
    """SimpleRateLimit must enforce the 10/sec hard SEC cap
    (永久边界 (i)). Drive an injected monotonic clock through 11
    consecutive ``wait`` calls; the 11th must sleep at least long
    enough for the oldest in-window call to slide out."""

    clock = itertools.count(start=0.0, step=0.05)  # 50ms per call
    sleeps: list[float] = []
    limiter = SimpleRateLimit(
        max_calls=10,
        period_sec=1.0,
        monotonic=lambda: next(clock),
        sleep=sleeps.append,
    )
    for _ in range(11):
        limiter.wait()
    # The first 10 calls fit in [0, 0.5s] window → no sleep needed for
    # any of them. Call 11 hits the cap and must sleep until the
    # oldest (timestamp 0.0) slides out of the 1.0-second window.
    assert len(sleeps) == 1
    assert sleeps[0] > 0
    assert sleeps[0] >= 0.4


def test_simple_rate_limit_validates_constructor_args() -> None:
    """Defensive: ``max_calls < 1`` or ``period_sec <= 0`` are
    construction errors, not silent no-ops."""

    with pytest.raises(ValueError):
        SimpleRateLimit(max_calls=0)
    with pytest.raises(ValueError):
        SimpleRateLimit(max_calls=10, period_sec=0)


def test_parse_companyfacts_rejects_payload_without_parsed_ratios() -> None:
    """A real SEC companyfacts payload does not include a
    ``parsed_ratios`` block; the F002 backfill driver synthesises it.
    Passing a raw SEC payload directly to ``parse_companyfacts`` must
    fail loudly so the caller sees the missing pre-processing step."""

    raw_sec_shape = {"cik": 320193, "entityName": "Apple Inc.", "facts": {}}
    with pytest.raises(ValueError) as exc_info:
        parse_companyfacts(
            "AAPL", raw_sec_shape, from_date=date(2014, 1, 1), to_date=date(2016, 1, 1)
        )
    assert "parsed_ratios" in str(exc_info.value)
    assert "AAPL" in str(exc_info.value)


def test_parse_companyfacts_rejects_missing_required_field() -> None:
    """SEC schema drift: if a synthesised ``parsed_ratios`` entry
    misses a required field, the parser must surface the offending
    fiscal_quarter context rather than silently dropping the row."""

    drift_payload = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "parsed_ratios": [
            {
                "ticker": "AAPL",
                "fiscal_quarter": "2014Q4",
                "fiscal_quarter_end": "2014-12-31",
                # report_date missing.
                "roe": 0.4469,
                "gross_margin": 0.4353,
                "fcf_yield": 0.0418,
                "debt_to_assets": 0.2952,
                "pe": 20.57,
                "pb": 12.54,
                "ev_ebitda": 16.72,
                "earnings_yield": 0.0486,
            }
        ],
    }
    with pytest.raises(ValueError) as exc_info:
        parse_companyfacts(
            "AAPL", drift_payload, from_date=date(2014, 1, 1), to_date=date(2016, 1, 1)
        )
    msg = str(exc_info.value)
    assert "report_date" in msg
    assert "2014Q4" in msg


def test_sec_concept_names_covers_eight_ratio_inputs() -> None:
    """Pinned for F002: the SEC us-gaap concept aliases must cover the
    full set of inputs the eight ratio formulas need so the F002
    driver has one canonical mapping."""

    expected_keys = {
        "net_income",
        "stockholders_equity",
        "revenues",
        "cogs",
        "cfo",
        "capex",
        "long_term_debt",
        "assets",
        "cash",
        "operating_income",
        "depreciation_amortization",
    }
    assert expected_keys.issubset(set(SEC_CONCEPT_NAMES))
    # Each entry is an alias chain (list of SEC concept names tried in
    # order); first element is the canonical name, additional entries
    # are SEC concept-rename / ASC standard transition fallbacks.
    assert SEC_CONCEPT_NAMES["net_income"][0] == "NetIncomeLoss"
    assert SEC_CONCEPT_NAMES["stockholders_equity"][0] == "StockholdersEquity"
    # Revenues alias chain must include the post-ASC 606 concept
    # (B029 F002 first-run discovered AAPL switched to this concept).
    assert (
        "RevenueFromContractWithCustomerExcludingAssessedTax"
        in SEC_CONCEPT_NAMES["revenues"]
    )

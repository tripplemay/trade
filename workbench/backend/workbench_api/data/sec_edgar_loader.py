"""SEC EDGAR companyfacts FundamentalsLoader.

B029 main-vendor adapter for ``data-source-evaluation-2026-05.md`` §6.2
(free SEC EDGAR XBRL ingest). Endpoints:

* Company facts API:
  ``https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json``
  Returns pre-parsed XBRL JSON (no raw XML required). The loader walks
  the per-concept ``units → USD`` arrays and matches entries by
  ``fp`` ∈ ``{Q1, Q2, Q3, FY}`` + ``form`` ∈ ``{10-Q, 10-K}``.
* Submissions (health probe):
  ``https://data.sec.gov/submissions/CIK{cik:010d}.json``

Hard constraints (永久边界 (h)(i), Planner 2026-05-26 spec §3):

* User-Agent header is required. SEC will ban the IP for 30 days
  without a contact email in the UA string. Format:
  ``Workbench Trade research-only <contact@example.com>``.
* Rate-limit 10 requests/second hard. Violations also trip a ban.
  :class:`SimpleRateLimit` enforces the cap in-process.
* No vendor SDK — ``httpx`` + stdlib ``json`` only (Planner pre-impl
  adjudication 2026-05-26 #4 — no new dep introduced).

Retry policy mirrors :class:`workbench_api.data.tiingo_loader.TiingoSnapshotLoader`:

* Up to 3 attempts; exponential backoff capped at 8 seconds.
* 5xx + 429 retry with backoff; 4xx other than 429 fails fast (config
  error — wrong CIK / malformed concept name).
* 403 surfaces as ``_AuthFailure`` so ``health_check`` returns False;
  on the fetch path a 403 indicates a missing / invalid User-Agent
  and propagates as the same exception so the caller sees the SEC
  rejection rather than a silent empty result.

The :func:`SECEDGARFundamentalsLoader.fetch_quarterly_fundamentals`
surface accepts a synthetic ticker (no CIK) by raising ``ValueError``
with a "skip in backfill driver" pointer (Planner pre-impl
adjudication 2026-05-26 #3 — F002 backfill driver catches and
``log warn + skip`` without aborting the batch).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import httpx

from workbench_api.data.fundamentals_loader import FundamentalsLoader, FundamentalsRow

logger = logging.getLogger(__name__)

SEC_EDGAR_BASE_URL = "https://data.sec.gov"
"""Public SEC EDGAR REST base. Pinned here so a SEC URL change is a
one-line edit, not a hunt across the codebase."""

DEFAULT_TIMEOUT_SECONDS: float = 30.0
MAX_RETRIES: int = 3
BACKOFF_BASE_SECONDS: float = 0.5
BACKOFF_CAP_SECONDS: float = 8.0

# SEC EDGAR fair-access hard limits (永久边界 (i)).
SEC_EDGAR_MAX_REQUESTS_PER_SECOND: int = 10

# Quarterly-period concept tag tuple used to filter companyfacts entries.
# SEC reports both calendar-quarter Q1/Q2/Q3 plus "FY" (annual) entries
# inside the same series; quarterly Q4 is derivable from FY - Q1 - Q2 - Q3.
_QUARTERLY_FP_VALUES: frozenset[str] = frozenset({"Q1", "Q2", "Q3", "Q4"})
_ANNUAL_FP_VALUES: frozenset[str] = frozenset({"FY"})
_ALLOWED_FORMS: frozenset[str] = frozenset({"10-K", "10-Q", "10-K/A", "10-Q/A"})


class _HttpClient(Protocol):
    """Subset of ``httpx.Client`` the loader actually uses.

    Hand-rolled stubs in unit tests inject this without inheriting
    from :class:`httpx.Client` (which would drag its real connection
    pool into the test path). Production constructor still builds a
    real ``httpx.Client``.
    """

    def get(self, url: str) -> Any: ...


class _Limiter(Protocol):
    """Subset of :class:`SimpleRateLimit` the loader invokes per call.

    Lets unit tests pass a no-op stub (e.g. ``lambda: None``) when the
    rate-limit behaviour is not under test, keeping the network-shape
    assertions isolated from the time-based limiter tests.
    """

    def wait(self) -> None: ...


class SimpleRateLimit:
    """In-process sliding-window rate limiter.

    Allows at most ``max_calls`` calls per ``period_sec`` seconds. When
    the limit is hit, :meth:`wait` sleeps just long enough for the
    oldest in-window call to slide out, then proceeds.

    Time + sleep are injectable so unit tests can drive the limiter
    through a scripted clock without real-time sleeps. Production
    callers use the defaults.
    """

    def __init__(
        self,
        max_calls: int,
        period_sec: float = 1.0,
        *,
        monotonic: Any = time.monotonic,
        sleep: Any = time.sleep,
    ) -> None:
        if max_calls < 1:
            raise ValueError(f"SimpleRateLimit max_calls must be >= 1, got {max_calls}")
        if period_sec <= 0:
            raise ValueError(
                f"SimpleRateLimit period_sec must be > 0, got {period_sec}"
            )
        self._max_calls = max_calls
        self._period_sec = period_sec
        self._monotonic = monotonic
        self._sleep = sleep
        self._timestamps: list[float] = []

    def wait(self) -> None:
        now = float(self._monotonic())
        cutoff = now - self._period_sec
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self._max_calls:
            oldest = self._timestamps[0]
            sleep_for = oldest + self._period_sec - now
            if sleep_for > 0:
                self._sleep(sleep_for)
            now = float(self._monotonic())
            cutoff = now - self._period_sec
            self._timestamps = [t for t in self._timestamps if t > cutoff]
        self._timestamps.append(now)


class SECEDGARFundamentalsLoader(FundamentalsLoader):
    """FundamentalsLoader backed by SEC EDGAR companyfacts API."""

    def __init__(
        self,
        contact_email: str | None = None,
        *,
        client: _HttpClient | None = None,
        limiter: _Limiter | None = None,
        sleep: Any = time.sleep,
        ticker_cik_map: dict[str, int | None] | None = None,
    ) -> None:
        """Bind the loader to a contact email + HTTP client + limiter.

        ``contact_email`` resolves from the explicit argument first,
        then the ``SEC_EDGAR_CONTACT_EMAIL`` environment variable.
        Missing email raises immediately with a fix pointer; the SEC
        will ban the source IP for 30 days without a valid User-Agent
        header (永久边界 (h)).

        ``client`` / ``limiter`` / ``sleep`` are injectable so unit
        tests can bypass the live network and the real ``time.sleep``
        (which would slow retry / rate-limit tests). Production
        callers use the defaults.

        ``ticker_cik_map`` defaults to the bundled
        ``workbench_api/data/fixtures/sec_edgar_responses/ticker_cik_map.json``
        — the B025 us_quality 30-ticker universe (27 real CIKs + 3
        synthetic ZQAI/ZQPT/ZQLH mapped to ``None``; pre-impl
        adjudication decision #3). Callers pass an override map when
        the backfill driver wants a wider universe (e.g. ADR proxies in
        a future batch).
        """

        resolved_email = contact_email or os.environ.get("SEC_EDGAR_CONTACT_EMAIL")
        if not resolved_email:
            raise RuntimeError(
                "SEC_EDGAR_CONTACT_EMAIL missing. SEC EDGAR requires a User-Agent "
                "header with a contact email (non-optional; ban IP otherwise — "
                "see https://www.sec.gov/os/accessing-edgar-data). Configure the "
                "GitHub repo secret SEC_EDGAR_CONTACT_EMAIL (Settings → Secrets "
                "and variables → Actions) so the workbench-deploy workflow can "
                "inject it into /etc/workbench/workbench.env via the "
                "EnvironmentFile mechanism, or set SEC_EDGAR_CONTACT_EMAIL in "
                "your local shell for `python -m pytest` runs that exercise the "
                "real loader path."
            )
        self._contact_email = resolved_email
        self._client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={
                "User-Agent": f"Workbench Trade research-only {self._contact_email}",
                "Accept": "application/json",
            },
        )
        self._limiter: _Limiter = limiter or SimpleRateLimit(
            SEC_EDGAR_MAX_REQUESTS_PER_SECOND, period_sec=1.0
        )
        self._sleep = sleep
        self._ticker_cik_map: dict[str, int | None] = (
            ticker_cik_map if ticker_cik_map is not None else _load_default_ticker_cik_map()
        )

    @property
    def contact_email(self) -> str:
        """Resolved SEC contact email. Exposed for diagnostics."""

        return self._contact_email

    @property
    def ticker_cik_map(self) -> dict[str, int | None]:
        """Resolved ticker → CIK mapping. Exposed for diagnostics and
        for the F002 backfill driver universe iteration."""

        return dict(self._ticker_cik_map)

    def fetch_quarterly_fundamentals(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[FundamentalsRow]:
        """Fetch all quarterly fundamentals **filed** in
        ``[from_date, to_date]`` inclusive for ``ticker``.

        Expects a pre-baked ``parsed_ratios`` block in the SEC payload
        (the F001 fixture shape). The B029 F002 backfill driver
        synthesises that block from the raw SEC companyfacts payload
        + Tiingo prices, then re-routes through this method via the
        :func:`parse_companyfacts` helper directly. Live SEC fetch
        without pre-parsing is exposed via
        :meth:`fetch_raw_companyfacts` for the driver to call.

        Raises :class:`ValueError` when ``ticker`` resolves to a
        synthetic entry (CIK ``None``) — the caller (F002 backfill
        driver) catches this and skips with a warn log per Planner
        pre-impl adjudication decision #3 (fail-safe; not a fatal).
        """

        payload = self.fetch_raw_companyfacts(ticker)
        return parse_companyfacts(ticker, payload, from_date=from_date, to_date=to_date)

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, Any]:
        """Fetch the **raw** SEC companyfacts JSON for ``ticker``.

        Returns the full ``data.sec.gov/api/xbrl/companyfacts/`` response
        as a typed dict (``cik`` / ``entityName`` / ``facts`` keys; the
        ``facts.us-gaap`` sub-tree carries every reported concept with
        its full unit / period array). The F002 backfill driver walks
        this tree to extract the eleven concepts pinned in
        :data:`SEC_CONCEPT_NAMES`, then computes the eight B025 ratios
        per fiscal quarter (joining Tiingo prices on ``report_date``).

        Synthetic-ticker handling and rate-limit invariants are the
        same as :meth:`fetch_quarterly_fundamentals`; the fetch path
        is shared.
        """

        if ticker not in self._ticker_cik_map:
            raise ValueError(
                f"Ticker {ticker!r} not in ticker_cik_map — extend "
                f"workbench_api/data/fixtures/sec_edgar_responses/"
                f"ticker_cik_map.json or pass an override map at "
                f"SECEDGARFundamentalsLoader construction."
            )
        cik = self._ticker_cik_map[ticker]
        if cik is None:
            raise ValueError(
                f"Synthetic ticker {ticker!r} has no SEC filing; "
                f"skip in backfill driver. (B025 fixture includes synthetic "
                f"universe entries — ZQAI/ZQPT/ZQLH — that never have real "
                f"SEC submissions; Planner pre-impl adjudication 2026-05-26 "
                f"decision #3 fail-safe pattern.)"
            )
        self._limiter.wait()
        url = f"{SEC_EDGAR_BASE_URL}/api/xbrl/companyfacts/CIK{cik:010d}.json"
        payload = self._get_with_retry(url)
        if not isinstance(payload, dict):
            raise ValueError(
                f"SEC companyfacts for {ticker} (CIK {cik}) returned non-dict "
                f"payload of type {type(payload).__name__}; cannot parse"
            )
        return payload

    def health_check(self) -> bool:
        """Probe SEC EDGAR by fetching AAPL submissions metadata.

        Returns ``True`` on a 200 response (UA accepted, network up);
        ``False`` on auth-shape rejection (403 — UA missing or banned
        IP). Network errors propagate so the caller can distinguish
        "SEC down" from "header rejected".
        """

        self._limiter.wait()
        try:
            self._get_with_retry(
                f"{SEC_EDGAR_BASE_URL}/submissions/CIK0000320193.json"
            )
        except _AuthFailure:
            return False
        return True

    def _get_with_retry(self, url: str) -> Any:
        """Issue GET with bounded retry on 5xx + 429.

        403 raises :class:`_AuthFailure` so :meth:`health_check` can
        distinguish "header rejected" from "vendor unreachable"
        without parsing exception types.
        """

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "sec_edgar_network_retry",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._sleep_for_attempt(attempt)
                continue

            status = response.status_code
            if status == 200:
                return response.json()
            if status == 403:
                raise _AuthFailure(
                    f"SEC EDGAR rejected request ({status}) — check User-Agent "
                    f"header / IP ban status (https://www.sec.gov/os/accessing-edgar-data)"
                )
            if status == 429 or 500 <= status < 600:
                last_error = httpx.HTTPStatusError(
                    f"SEC EDGAR {status}", request=response.request, response=response
                )
                logger.warning(
                    "sec_edgar_status_retry",
                    extra={"url": url, "status": status, "attempt": attempt + 1},
                )
                self._sleep_for_attempt(attempt)
                continue
            response.raise_for_status()
        assert last_error is not None  # noqa: S101 — logic-protected branch
        logger.error(
            "sec_edgar_retries_exhausted",
            extra={"url": url, "attempts": MAX_RETRIES, "error": str(last_error)},
        )
        raise last_error

    def _sleep_for_attempt(self, attempt: int) -> None:
        delay = min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_CAP_SECONDS)
        self._sleep(delay)


class _AuthFailure(RuntimeError):
    """Raised when SEC EDGAR returns 403 (UA missing / banned IP).

    Kept private so the public surface is just
    ``health_check() -> bool`` + ``fetch_quarterly_fundamentals``
    raising standard ``httpx`` errors. Auth failures during the fetch
    path propagate as well — they indicate a real misconfiguration the
    caller must surface.
    """


def parse_companyfacts(
    ticker: str,
    payload: dict[str, Any],
    *,
    from_date: date,
    to_date: date,
) -> list[FundamentalsRow]:
    """Convert a SEC companyfacts JSON dict into a list of
    :class:`FundamentalsRow` in filing-date order.

    Per-quarter ratio computation needs MarketCap (price × shares) which
    is not in the companyfacts payload — for F001 we surface only the
    quarters whose ``parsed_ratios`` block is pre-baked into the
    fixture under the ``parsed_ratios`` top-level key. The B029 F002
    backfill driver fills the gap by stitching live Tiingo prices into
    the same shape before persistence.

    The fixture format the loader recognises:

    .. code-block:: json

        {
          "cik": 320193,
          "entityName": "Apple Inc.",
          "parsed_ratios": [
            {
              "ticker": "AAPL", "fiscal_quarter": "2014Q4",
              "fiscal_quarter_end": "2014-12-27", "report_date": "2015-01-28",
              "roe": 0.4469, "gross_margin": 0.4353, ...
            }
          ]
        }

    Real SEC companyfacts payloads do not include ``parsed_ratios``;
    the F002 backfill driver synthesises this block before passing the
    composite dict here. F001 ships with the synthesised fixtures so
    the unit tests can exercise the parser without network access.

    Missing required fields raise ``ValueError`` with the offending
    fiscal_quarter context so a SEC schema drift fails loudly.
    """

    rows_raw = payload.get("parsed_ratios")
    if rows_raw is None:
        raise ValueError(
            f"SEC companyfacts payload for {ticker} missing the "
            f"``parsed_ratios`` block. The F002 backfill driver must "
            f"compute eight ratios per quarter (via xbrl_parser.compute_*) "
            f"and inject the list before invoking parse_companyfacts. "
            f"Fixture format documented in parse_companyfacts docstring."
        )
    if not isinstance(rows_raw, list):
        raise ValueError(
            f"SEC companyfacts payload for {ticker} ``parsed_ratios`` is not "
            f"a list (got {type(rows_raw).__name__})"
        )
    required = (
        "ticker",
        "fiscal_quarter",
        "fiscal_quarter_end",
        "report_date",
        "roe",
        "gross_margin",
        "fcf_yield",
        "debt_to_assets",
        "pe",
        "pb",
        "ev_ebitda",
        "earnings_yield",
    )
    out: list[FundamentalsRow] = []
    for entry in rows_raw:
        if not isinstance(entry, dict):
            raise ValueError(
                f"SEC companyfacts ``parsed_ratios`` entry for {ticker} is not "
                f"a dict (got {type(entry).__name__})"
            )
        missing = [key for key in required if key not in entry]
        if missing:
            raise ValueError(
                f"SEC companyfacts ``parsed_ratios`` entry for {ticker} "
                f"fiscal_quarter={entry.get('fiscal_quarter', '?')} missing "
                f"fields {missing}; got keys {sorted(entry.keys())}"
            )
        report_dt = date.fromisoformat(str(entry["report_date"]))
        if report_dt < from_date or report_dt > to_date:
            continue
        out.append(
            FundamentalsRow(
                report_date=report_dt,
                ticker=str(entry["ticker"]),
                fiscal_quarter=str(entry["fiscal_quarter"]),
                fiscal_quarter_end=date.fromisoformat(str(entry["fiscal_quarter_end"])),
                roe=float(entry["roe"]),
                gross_margin=float(entry["gross_margin"]),
                fcf_yield=float(entry["fcf_yield"]),
                debt_to_assets=float(entry["debt_to_assets"]),
                pe=float(entry["pe"]),
                pb=float(entry["pb"]),
                ev_ebitda=float(entry["ev_ebitda"]),
                earnings_yield=float(entry["earnings_yield"]),
            )
        )
    out.sort(key=lambda r: r.report_date)
    return out


def _load_default_ticker_cik_map() -> dict[str, int | None]:
    """Read the bundled ``ticker_cik_map.json`` fixture.

    The fixture is git-tracked and covers the B025 us_quality_momentum
    30-ticker universe (27 real CIKs + 3 synthetic ZQAI/ZQPT/ZQLH
    mapped to ``null``). Callers that want a wider universe pass an
    override map at construction.
    """

    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "sec_edgar_responses"
        / "ticker_cik_map.json"
    )
    raw: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    out: dict[str, int | None] = {}
    for ticker, cik in raw.items():
        # Skip underscore-prefixed sentinel keys (e.g. ``_doc`` which
        # documents the fixture inline; JSON lacks comments).
        if ticker.startswith("_"):
            continue
        if cik is None:
            out[ticker] = None
        else:
            out[ticker] = int(cik)
    return out


# Concept-name **alias chains** for downstream F002 use. F001 doesn't
# traverse raw companyfacts at the concept level (the fixtures already
# pre-bake the eight ratios via ``parsed_ratios``), but F002's backfill
# driver walks these to extract fact values from the live SEC payload.
# Pinned here so a SEC concept rename / ASC standard transition has
# one edit point.
#
# Each ratio input maps to an **ordered list** of SEC us-gaap concept
# names; the F002 parser tries them in order and merges every entry
# from any concept whose name matches. Per-(year, quarter) bucketing
# then keeps the latest-filed entry, so an alias chain effectively
# stitches together a single time series across the SEC's concept
# renaming history.
#
# Common drift causes the chains address:
#
# * **Revenues** — pre-ASC 606 filings used ``Revenues`` /
#   ``SalesRevenueNet``; post-2018 ASC 606 filings switched to
#   ``RevenueFromContractWithCustomerExcludingAssessedTax``. Most B025
#   universe tickers (AAPL, MSFT, NVDA, ...) have ≤ 10 Revenues entries
#   total and the rest under the new concept (B029 F002 first-run
#   discovered this on AAPL).
# * **COGS** — some filers use ``CostOfGoodsAndServicesSold``, others
#   ``CostOfRevenue`` or ``CostOfGoodsSold``.
# * **LongTermDebt** — sometimes filed as
#   ``LongTermDebtNoncurrent`` for the non-current portion only.
# * **DepreciationDepletionAndAmortization** — different filers use
#   ``DepreciationAndAmortization`` or just ``Depreciation``.
# * **PaymentsToAcquirePropertyPlantAndEquipment** — some filers report
#   capex as ``PaymentsToAcquireProductiveAssets``.
SEC_CONCEPT_NAMES: dict[str, list[str]] = {
    "net_income": ["NetIncomeLoss"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "revenues": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "cogs": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfServices",
        "CostsAndExpenses",
        # Utilities + service firms report operating expenses as a
        # single line item rather than splitting COGS / OpEx (e.g. NEE,
        # LIN, financial firms). Treating ``OperatingExpenses`` as a
        # COGS-equivalent imprecisely inflates gross_margin denominator
        # but unlocks ratio production for non-product filers.
        "OperatingExpenses",
        "OperatingCostsAndExpenses",
    ],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
        "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "assets": ["Assets"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        # Pre-tax income — not strictly equivalent (includes non-operating
        # interest income/expense), but the closest XBRL fallback for
        # filers that stop reporting OperatingIncomeLoss (e.g. JNJ
        # post-2015 transitions to this concept). Documented imprecision.
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
}
"""SEC us-gaap XBRL concept-name **alias chains** per ratio input.

For each input, the F002 driver tries every concept in order and
merges all matching entries before bucketing by calendar quarter. This
handles the common SEC concept drift between ASC standards / filer
preferences without forcing every filer to use one canonical name.
"""


def quarterly_fp_values() -> frozenset[str]:
    """Return the SEC ``fp`` (fiscal period) tokens treated as quarterly.

    Exposed for the F002 backfill driver's filter loop; tests assert
    the canonical set is the four-quarter tuple plus an annual fall-back
    documented in :data:`_QUARTERLY_FP_VALUES`.
    """

    return _QUARTERLY_FP_VALUES


def annual_fp_values() -> frozenset[str]:
    """Return the SEC ``fp`` tokens for annual filings (FY)."""

    return _ANNUAL_FP_VALUES


def allowed_forms() -> frozenset[str]:
    """Return the SEC ``form`` tokens recognised for fundamentals."""

    return _ALLOWED_FORMS

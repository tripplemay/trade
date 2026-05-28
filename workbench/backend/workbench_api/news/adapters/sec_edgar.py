"""B033 F002 — SEC EDGAR news adapter.

Fetches SEC filings (``10-K`` / ``10-Q`` / ``8-K`` / ``4``) from the
EDGAR ``/submissions/CIK*.json`` endpoint, builds :class:`NewsItem`
rows, and yields them for the F003 CLI to persist via
:class:`workbench_api.db.repositories.news.NewsRepository`. The
adapter reuses B029's User-Agent + 10-req/sec rate-limit pattern via
the shared :class:`SimpleRateLimit` class so the workbench stays under
the SEC fair-access cap regardless of which loader is active.

Hard constraints inherited from B029 (永久边界 (h)(i)):
- User-Agent must carry a contact email. Source: ``SEC_EDGAR_CONTACT_EMAIL``
  env / GitHub secret. Unset → constructor raises with a fix pointer.
- Max 10 requests/second — :class:`SimpleRateLimit` enforces in-process.
- Synthetic ZQ* tickers skip with a warn log (no SEC filing exists).
  Same pattern as :class:`SECEDGARFundamentalsLoader`.

B033 boundaries (永久边界 (p)):
- Raw filing body is **never** persisted in DB. The adapter fetches the
  primary document, hands it to the snapshot writer, and stores only
  ``snapshot_path`` + ``content_sha256`` on the ``news`` row.
- Adapter does **not** persist or write snapshots itself; the CLI
  composes adapter → snapshot writer → repository. This keeps the
  adapter a pure transformation that a unit test can drive with a
  fake HTTP client + ``tmp_path``.

The ``/submissions/`` envelope was live-validated against AAPL
(CIK 0000320193) on 2026-05-28. The shape:

.. code-block:: text

    {
      "cik": "0000320193", "name": "Apple Inc.", "tickers": [...],
      "filings": {
        "recent": {
          "accessionNumber": [...],    # parallel arrays
          "filingDate": [...],         # YYYY-MM-DD
          "form": [...],               # "10-K" / "10-Q" / "8-K" / "4" / ...
          "primaryDocument": [...],    # filename inside the accession bundle
          "primaryDocDescription": [...],
          "reportDate": [...],         # YYYY-MM-DD, "" for forms without
        },
        "files": [...]                 # older filings; not walked in F002
      }
    }

:func:`test_sec_edgar_submissions_envelope_field_paths` (in
``tests/unit/test_news_adapter_edgar.py``) pins these paths so a SEC
schema change fails loudly.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from workbench_api.data.sec_edgar_loader import (
    SEC_EDGAR_BASE_URL,
    SEC_EDGAR_MAX_REQUESTS_PER_SECOND,
    SimpleRateLimit,
)
from workbench_api.news.adapters.base import NewsItem

logger = logging.getLogger(__name__)


# Form types this adapter ingests (spec §4.4). The CLI in F003 lets the
# user narrow this set via ``--form-types``; outside that override the
# adapter walks all four. Form ``4`` is the insider-transaction form;
# the SEC encodes it without a hyphen (``4`` not ``Form 4``) — confirmed
# in the live envelope sample on 2026-05-28.
DEFAULT_FORM_TYPES: frozenset[str] = frozenset({"10-K", "10-Q", "8-K", "4"})


class _HttpClient(Protocol):
    """Subset of :class:`httpx.Client` the adapter uses.

    Unit tests inject a fake without inheriting from ``httpx.Client``
    (which would drag its real connection pool into the test path).
    Production builds a real ``httpx.Client`` in :py:meth:`__init__`.
    """

    def get(self, url: str) -> Any: ...


class _Limiter(Protocol):
    """Subset of :class:`SimpleRateLimit` the adapter invokes per call.

    Tests pass a no-op stub when the rate-limit behaviour is not under
    test, keeping the network-shape assertions isolated from the
    time-based limiter checks.
    """

    def wait(self) -> None: ...


@dataclass(frozen=True, slots=True)
class _ParsedFiling:
    """One filing row pulled out of the ``filings.recent`` parallel arrays.

    Kept private to this module — it's an intermediate step between the
    raw EDGAR envelope and the :class:`NewsItem` rows the adapter
    yields. Pre-filter on form / date happens before primary-doc fetch
    so the rate limiter only spends quota on items we actually want.
    """

    accession_number: str
    form: str
    filing_date: str  # YYYY-MM-DD
    report_date: str  # YYYY-MM-DD or ""
    primary_document: str
    primary_doc_description: str
    items: str


def _load_default_ticker_cik_map() -> dict[str, int | None]:
    """Reuse B029's bundled CIK fixture (avoid duplicate maintenance)."""

    from workbench_api.data.sec_edgar_loader import _load_default_ticker_cik_map as _b029

    return _b029()


class SECEdgarNewsAdapter:
    """SEC EDGAR ``/submissions/`` adapter.

    Construction mirrors :class:`SECEDGARFundamentalsLoader` (B029) so
    operators using both adapters configure them the same way:

    - ``contact_email`` resolves from the argument first, then
      ``SEC_EDGAR_CONTACT_EMAIL`` env var. Unset raises.
    - ``client`` / ``limiter`` are injectable for unit tests.
    - ``ticker_cik_map`` defaults to the B025 27-real + 3-synthetic
      map. Synthetic entries (``ZQ*``) have CIK ``None``; fetch logs
      warn + returns empty for them (same fail-safe pattern).
    - ``form_types`` defaults to :data:`DEFAULT_FORM_TYPES`. The F003
      CLI passes a narrowed set when ``--form-types`` is supplied.
    """

    source: str = "sec_edgar"

    def __init__(
        self,
        *,
        contact_email: str | None = None,
        client: _HttpClient | None = None,
        limiter: _Limiter | None = None,
        ticker_cik_map: dict[str, int | None] | None = None,
        form_types: Iterable[str] | None = None,
    ) -> None:
        resolved_email = contact_email or os.environ.get("SEC_EDGAR_CONTACT_EMAIL")
        if not resolved_email:
            raise RuntimeError(
                "SEC_EDGAR_CONTACT_EMAIL missing. SEC EDGAR requires a User-Agent "
                "header with a contact email (永久边界 (h)). Configure the "
                "GitHub repo secret SEC_EDGAR_CONTACT_EMAIL or export it in the "
                "local shell before running `python -m workbench_api.news.cli "
                "fetch --source edgar`."
            )
        self._contact_email = resolved_email
        self._client = client or httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": f"Workbench Trade research-only {self._contact_email}",
                "Accept": "application/json",
            },
        )
        self._limiter: _Limiter = limiter or SimpleRateLimit(
            SEC_EDGAR_MAX_REQUESTS_PER_SECOND, period_sec=1.0
        )
        self._ticker_cik_map: dict[str, int | None] = (
            ticker_cik_map if ticker_cik_map is not None else _load_default_ticker_cik_map()
        )
        self._form_types: frozenset[str] = (
            frozenset(form_types) if form_types is not None else DEFAULT_FORM_TYPES
        )

    @property
    def contact_email(self) -> str:
        return self._contact_email

    @property
    def form_types(self) -> frozenset[str]:
        return self._form_types

    def fetch(self, *, ticker: str, since: datetime) -> Iterable[NewsItem]:
        """Yield :class:`NewsItem`s for ``ticker`` filed on/after ``since``.

        ``since`` is interpreted at the **filing date** boundary — the
        SEC reports filing dates as ``YYYY-MM-DD`` strings; the adapter
        casts ``since`` to a date for comparison. A filing on the exact
        ``since`` day is included.

        Synthetic tickers (CIK ``None``) yield nothing and log a warn.
        Unknown tickers raise ``KeyError`` with the universe-extension
        pointer — silent skip would hide a typo in the CLI's
        ``--ticker`` flag.
        """

        if ticker not in self._ticker_cik_map:
            raise KeyError(
                f"Ticker {ticker!r} not in ticker_cik_map. Extend "
                "workbench_api/data/fixtures/sec_edgar_responses/"
                "ticker_cik_map.json or pass an override map at "
                "SECEdgarNewsAdapter construction."
            )
        cik = self._ticker_cik_map[ticker]
        if cik is None:
            logger.warning(
                "sec_edgar_news_skip_synthetic",
                extra={"ticker": ticker, "reason": "no SEC filings for synthetic universe entry"},
            )
            return iter(())
        return self._fetch_resolved(ticker=ticker, cik=cik, since=since)

    def _fetch_resolved(
        self, *, ticker: str, cik: int, since: datetime
    ) -> Iterator[NewsItem]:
        since_date_iso = since.date().isoformat()
        envelope = self._fetch_submissions(cik)
        entity_name = str(envelope.get("name") or envelope.get("entityName") or ticker)
        filings = self._iter_recent_filings(envelope)
        for filing in filings:
            if filing.form not in self._form_types:
                continue
            if filing.filing_date < since_date_iso:
                continue
            yield self._build_item(
                ticker=ticker,
                cik=cik,
                entity_name=entity_name,
                filing=filing,
            )

    def _fetch_submissions(self, cik: int) -> dict[str, Any]:
        self._limiter.wait()
        url = f"{SEC_EDGAR_BASE_URL}/submissions/CIK{cik:010d}.json"
        response = self._client.get(url)
        status = getattr(response, "status_code", 200)
        if status != 200:
            raise RuntimeError(
                f"SEC EDGAR /submissions/ returned {status} for CIK{cik:010d}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(
                f"SEC EDGAR /submissions/ payload is not a dict (got "
                f"{type(payload).__name__})"
            )
        return payload

    def _iter_recent_filings(self, envelope: dict[str, Any]) -> Iterator[_ParsedFiling]:
        filings_block = envelope.get("filings")
        if not isinstance(filings_block, dict):
            raise ValueError(
                "SEC EDGAR /submissions/ envelope is missing the ``filings`` "
                "object (live-validated field path; SEC schema drift?)"
            )
        recent = filings_block.get("recent")
        if not isinstance(recent, dict):
            raise ValueError(
                "SEC EDGAR /submissions/ envelope is missing ``filings.recent`` "
                "(live-validated field path; SEC schema drift?)"
            )
        forms = recent.get("form", [])
        accs = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])
        primary_descs = recent.get("primaryDocDescription", [])
        items = recent.get("items", [])
        n = len(accs)
        if not all(len(arr) == n for arr in (forms, filing_dates, primary_docs)):
            raise ValueError(
                "SEC EDGAR /submissions/ parallel arrays in ``filings.recent`` "
                "are not the same length (live-validated invariant; SEC schema "
                "drift?)"
            )
        for i in range(n):
            yield _ParsedFiling(
                accession_number=str(accs[i]),
                form=str(forms[i]),
                filing_date=str(filing_dates[i]),
                report_date=str(report_dates[i]) if i < len(report_dates) else "",
                primary_document=str(primary_docs[i]),
                primary_doc_description=(
                    str(primary_descs[i]) if i < len(primary_descs) else ""
                ),
                items=str(items[i]) if i < len(items) else "",
            )

    def _build_item(
        self,
        *,
        ticker: str,
        cik: int,
        entity_name: str,
        filing: _ParsedFiling,
    ) -> NewsItem:
        accession_compact = filing.accession_number.replace("-", "")
        primary_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_compact}/"
            f"{filing.primary_document}"
        )
        # Per-filing index page (canonical SEC landing). This is what
        # B034 / B036 will deep-link to in the Recommendations UI; the
        # primary doc URL is recoverable from it but the index is the
        # human-friendly entry point.
        filing_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={cik:010d}&type={filing.form}&dateb=&owner=include&count=40"
        )
        raw_body = self._fetch_primary_document(primary_url)
        ext = self._infer_extension(filing.form, filing.primary_document)
        published_at = self._parse_filing_date(filing.filing_date)
        title = self._build_title(entity_name, filing)
        summary = filing.primary_doc_description or None
        return NewsItem(
            source=self.source,
            source_id=filing.accession_number,
            url=filing_url,
            title=title,
            summary=summary,
            ticker=ticker,
            form_type=filing.form,
            published_at=published_at,
            raw_body=raw_body,
            raw_ext=ext,
        )

    def _fetch_primary_document(self, url: str) -> bytes:
        self._limiter.wait()
        response = self._client.get(url)
        status = getattr(response, "status_code", 200)
        if status != 200:
            raise RuntimeError(
                f"SEC EDGAR primary doc fetch returned {status}: {url}"
            )
        body = response.content
        if not isinstance(body, bytes):
            raise TypeError(
                f"SEC EDGAR primary doc body is not bytes (got "
                f"{type(body).__name__}); test fake must populate "
                "``response.content``"
            )
        return body

    @staticmethod
    def _infer_extension(form: str, primary_document: str) -> str:
        """Form 4 uses XML; the 10-K/Q/8-K filings publish as HTML.

        Falls back to the actual filename extension when one is present
        so a future SEC change (e.g. inline-XBRL ``.htm`` rename to
        ``.html``) round-trips correctly.
        """

        if "." in primary_document:
            ext = primary_document.rsplit(".", 1)[-1].lower()
            if ext:
                return ext
        return "xml" if form == "4" else "htm"

    @staticmethod
    def _parse_filing_date(filing_date_iso: str) -> datetime:
        """Treat the SEC filing date as midnight UTC.

        SEC reports filings as a date without a time; the workbench's
        ``published_at`` column is timezone-aware, so a deterministic
        UTC midnight gives us a sortable value without inventing a
        time-of-day.
        """

        try:
            year, month, day = (int(p) for p in filing_date_iso.split("-"))
        except ValueError as exc:
            raise ValueError(
                f"SEC EDGAR filing date {filing_date_iso!r} is not in "
                "YYYY-MM-DD form (live-validated invariant; schema drift?)"
            ) from exc
        return datetime(year, month, day, tzinfo=UTC)

    @staticmethod
    def _build_title(entity_name: str, filing: _ParsedFiling) -> str:
        date_suffix = filing.report_date or filing.filing_date
        title = f"{entity_name} — {filing.form} ({date_suffix})"
        if filing.items:
            title = f"{title} [{filing.items}]"
        return title

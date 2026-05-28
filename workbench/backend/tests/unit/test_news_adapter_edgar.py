"""B033 F002 — SECEdgarNewsAdapter fixture round-trip + form filter +
rate limit + User-Agent + ZQ* skip + envelope schema pinning.

Adapter is tested via a fake :class:`httpx.Client` (the ``_HttpClient``
Protocol). The fake serves up the B033 fixture envelopes for the
``/submissions/`` calls and the bundled primary-document samples for
the body fetches. No real network access — fixture-first per the
spec's CI strategy.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from workbench_api.news.adapters.sec_edgar import (
    DEFAULT_FORM_TYPES,
    SECEdgarNewsAdapter,
)
from workbench_api.news.snapshot import NewsSnapshotWriter

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "news"

AAPL_CIK = 320193
NVDA_CIK = 1045810
MSFT_CIK = 789019


def _load_fixture(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@dataclass
class _FakeResponse:
    """Minimal subset of :class:`httpx.Response` used by the adapter."""

    status_code: int = 200
    _payload: Any = None
    _body: bytes = b""

    def json(self) -> Any:
        return self._payload

    @property
    def content(self) -> bytes:
        return self._body


class _FakeClient:
    """Routes adapter GETs to fixture payloads + records the call timeline.

    A real ``httpx.Client`` is overkill here — the adapter only calls
    :meth:`get` and reads ``response.json()`` / ``response.content``.
    """

    def __init__(
        self,
        submission_payloads: dict[int, dict[str, Any]] | None = None,
        primary_bodies: dict[str, bytes] | None = None,
        default_primary_body: bytes = b"<html>default body</html>",
    ) -> None:
        self.submission_payloads = submission_payloads or {}
        self.primary_bodies = primary_bodies or {}
        self.default_primary_body = default_primary_body
        self.requests: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str) -> _FakeResponse:
        self.requests.append(url)
        for cik, payload in self.submission_payloads.items():
            if f"CIK{cik:010d}.json" in url:
                return _FakeResponse(status_code=200, _payload=payload)
        for key, body in self.primary_bodies.items():
            if key in url:
                return _FakeResponse(status_code=200, _body=body)
        if "/Archives/edgar/data/" in url:
            return _FakeResponse(
                status_code=200, _body=self.default_primary_body
            )
        return _FakeResponse(status_code=404, _payload={"error": "not found"})


class _RecordingLimiter:
    """No-sleep limiter that counts ``wait()`` calls."""

    def __init__(self) -> None:
        self.calls = 0

    def wait(self) -> None:
        self.calls += 1


def _make_adapter(
    *,
    client: _FakeClient,
    form_types: Iterable[str] | None = None,
    limiter: _RecordingLimiter | None = None,
) -> tuple[SECEdgarNewsAdapter, _RecordingLimiter]:
    actual_limiter = limiter or _RecordingLimiter()
    adapter = SECEdgarNewsAdapter(
        contact_email="news-test@example.com",
        client=client,
        limiter=actual_limiter,
        ticker_cik_map={
            "AAPL": AAPL_CIK,
            "NVDA": NVDA_CIK,
            "MSFT": MSFT_CIK,
            "ZQAI": None,
        },
        form_types=form_types,
    )
    return adapter, actual_limiter


def test_fetch_aapl_filters_to_allowed_forms() -> None:
    """Fixture deliberately seeds S-1 + 13F-HR noise. The adapter must
    drop them and only yield the 10-K / 10-Q / 8-K / 4 entries."""

    client = _FakeClient(
        submission_payloads={AAPL_CIK: _load_fixture("edgar-submissions-AAPL.json")},
    )
    adapter, _ = _make_adapter(client=client)
    items = list(
        adapter.fetch(
            ticker="AAPL",
            since=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    forms = sorted({item.form_type for item in items if item.form_type is not None})
    assert forms == ["10-K", "10-Q", "4", "8-K"]
    accs = sorted(item.source_id for item in items)
    # Verify the noise (S-1 + 13F-HR accession numbers) is excluded.
    assert "0000999999-26-000001" not in accs
    assert "0000888888-26-000001" not in accs


def test_fetch_form_types_override_narrows_set() -> None:
    """F003 CLI ``--form-types 10-K`` flag should yield only 10-Ks."""

    client = _FakeClient(
        submission_payloads={AAPL_CIK: _load_fixture("edgar-submissions-AAPL.json")},
    )
    adapter, _ = _make_adapter(client=client, form_types={"10-K"})
    items = list(
        adapter.fetch(
            ticker="AAPL",
            since=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    forms = {item.form_type for item in items}
    assert forms == {"10-K"}
    assert len(items) == 2  # Two 10-K filings in the AAPL fixture.


def test_fetch_since_filter_excludes_older_filings() -> None:
    """The 2025-11-01 10-K in the fixture must drop out when ``since``
    is set to 2026-04-01."""

    client = _FakeClient(
        submission_payloads={AAPL_CIK: _load_fixture("edgar-submissions-AAPL.json")},
    )
    adapter, _ = _make_adapter(client=client)
    items = list(
        adapter.fetch(
            ticker="AAPL",
            since=datetime(2026, 4, 1, tzinfo=UTC),
        )
    )
    dates = sorted(item.published_at.date().isoformat() for item in items)
    assert "2025-11-01" not in dates
    # All retained dates must be >= since.
    assert all(d >= "2026-04-01" for d in dates)


def test_fetch_builds_news_item_fields_correctly() -> None:
    """Pin the exact NewsItem shape for an 8-K + Form 4 + 10-K."""

    client = _FakeClient(
        submission_payloads={AAPL_CIK: _load_fixture("edgar-submissions-AAPL.json")},
    )
    adapter, _ = _make_adapter(client=client)
    items = {
        item.source_id: item
        for item in adapter.fetch(
            ticker="AAPL",
            since=datetime(2026, 4, 1, tzinfo=UTC),
        )
    }
    ten_k = items["0000320193-26-000020"]
    assert ten_k.source == "sec_edgar"
    assert ten_k.form_type == "10-K"
    assert ten_k.ticker == "AAPL"
    assert ten_k.summary == "10-K"
    assert ten_k.raw_ext == "htm"
    assert ten_k.url.startswith(
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    )
    assert "Apple Inc." in ten_k.title
    assert "10-K" in ten_k.title

    form_4 = items["0001140361-26-020871"]
    assert form_4.form_type == "4"
    assert form_4.raw_ext == "xml"
    assert form_4.summary == "FORM 4"

    eight_k = items["0000320193-26-000011"]
    assert eight_k.form_type == "8-K"
    # 8-K items code roll into the title for B034 cite UI readability.
    assert "[2.02,9.01]" in eight_k.title


def test_synthetic_ticker_yields_nothing_and_logs_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ZQ* synthetic tickers have CIK None and never have SEC filings
    (B025 universe convention; same skip pattern as B029)."""

    client = _FakeClient()
    adapter, _ = _make_adapter(client=client)
    with caplog.at_level(logging.WARNING):
        items = list(
            adapter.fetch(
                ticker="ZQAI",
                since=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    assert items == []
    assert any(
        "sec_edgar_news_skip_synthetic" in record.message
        or record.message == "sec_edgar_news_skip_synthetic"
        for record in caplog.records
    )
    # No HTTP request should have been issued for a synthetic ticker.
    assert client.requests == []


def test_unknown_ticker_raises_with_universe_pointer() -> None:
    client = _FakeClient()
    adapter, _ = _make_adapter(client=client)
    with pytest.raises(KeyError, match="ticker_cik_map"):
        list(
            adapter.fetch(
                ticker="UNKNOWN_TICKER",
                since=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )


def test_rate_limiter_runs_before_every_http_call() -> None:
    """Adapter must call ``limiter.wait()`` ahead of submissions fetch +
    each primary-document fetch — the SEC fair-access cap is shared
    across all GETs (永久边界 (i))."""

    client = _FakeClient(
        submission_payloads={NVDA_CIK: _load_fixture("edgar-submissions-NVDA.json")},
    )
    adapter, limiter = _make_adapter(client=client)
    items = list(
        adapter.fetch(
            ticker="NVDA",
            since=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    # 1 submissions GET + 1 GET per filing (NVDA fixture has 3 filings,
    # all in allowed forms; one is filtered by date if applicable —
    # since=2026-01-01 keeps all three).
    assert len(items) == 3
    assert limiter.calls == 1 + len(items)
    assert sum(1 for url in client.requests if "/submissions/" in url) == 1


def test_user_agent_header_contains_contact_email() -> None:
    """Constructor must build an httpx.Client with the SEC-required UA;
    we read it off the client when no override is injected."""

    import httpx

    adapter = SECEdgarNewsAdapter(contact_email="abc@example.com")
    client = adapter._client  # noqa: SLF001 — intentional internal access for test
    assert isinstance(client, httpx.Client)
    ua = client.headers["User-Agent"]
    assert "abc@example.com" in ua
    assert "Workbench Trade" in ua


def test_constructor_raises_when_contact_email_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEC_EDGAR_CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="SEC_EDGAR_CONTACT_EMAIL missing"):
        SECEdgarNewsAdapter()


def test_sec_edgar_submissions_envelope_field_paths() -> None:
    """Pin the SEC ``/submissions/`` envelope shape the adapter relies on.

    Live-validated against ``CIK0000320193.json`` (Apple) on 2026-05-28.
    If SEC adds / renames / moves any of these paths, the adapter starts
    yielding empty results silently — this test fails loud instead.
    """

    payload = _load_fixture("edgar-submissions-AAPL.json")
    assert isinstance(payload.get("cik"), str)
    # Either ``name`` (current envelope) or ``entityName`` (older docs).
    assert payload.get("name") or payload.get("entityName")
    filings = payload["filings"]
    recent = filings["recent"]
    required_arrays = (
        "accessionNumber",
        "filingDate",
        "form",
        "primaryDocument",
        "primaryDocDescription",
        "reportDate",
        "items",
    )
    n = len(recent["accessionNumber"])
    for key in required_arrays:
        assert key in recent, f"SEC envelope drift: missing {key!r}"
        assert isinstance(recent[key], list), f"{key} is not a list"
        assert len(recent[key]) == n, f"{key} array length drift"


def test_fetch_writes_snapshot_and_persists_via_repository(
    initialised_db: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """End-to-end-ish: adapter → snapshot writer → repository.

    Exercises the production composition: the CLI in F003 will run this
    exact sequence. We verify (a) the snapshot file lands at the
    expected partitioned path, (b) the repository row references it,
    and (c) ``content_sha256`` matches the body we wrote."""

    import hashlib

    from sqlalchemy.orm import sessionmaker

    from workbench_api.db.engine import get_engine
    from workbench_api.db.repositories.news import NewsRepository

    nvda_envelope = _load_fixture("edgar-submissions-NVDA.json")
    body = (FIXTURE_DIR / "edgar-primary-8k-NVDA.htm").read_bytes()
    client = _FakeClient(
        submission_payloads={NVDA_CIK: nvda_envelope},
        primary_bodies={"nvda-20260427.htm": body},
    )
    adapter, _ = _make_adapter(client=client)
    snapshot_root = tmp_path / "snapshots"
    writer = NewsSnapshotWriter(snapshot_root)
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        repo = NewsRepository(session)
        first_8k = next(
            item
            for item in adapter.fetch(
                ticker="NVDA",
                since=datetime(2026, 1, 1, tzinfo=UTC),
            )
            if item.form_type == "8-K"
        )
        snap = writer.write(
            source=first_8k.source,
            published_on=first_8k.published_at.date(),
            identifier=first_8k.source_id,
            body=first_8k.raw_body,
            ext=first_8k.raw_ext,
        )
        row = repo.save_if_new(
            first_8k,
            snapshot_path=snap.relative_path,
            content_sha256=snap.content_sha256,
        )
        assert row is not None
        assert row.snapshot_path == snap.relative_path
        assert row.content_sha256 == hashlib.sha256(body).hexdigest()
        on_disk = snapshot_root / snap.relative_path
        assert on_disk.is_file()
        assert on_disk.read_bytes() == body
    finally:
        session.close()


def test_default_form_types_match_spec() -> None:
    """Spec §4.4 pins the form set to {10-K, 10-Q, 8-K, 4}; a future
    edit must update both the spec and this constant in lockstep."""

    assert frozenset({"10-K", "10-Q", "8-K", "4"}) == DEFAULT_FORM_TYPES

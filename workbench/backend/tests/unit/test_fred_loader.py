"""B035 F001 — FRED market-context adapter (offline, stub httpx).

Pins the envelope contract (per the FRED API docs; the endpoint path was
live-validated 2026-06-04 via the no-key 400 response — full success
envelope is validated at L2 once a real FRED_API_KEY is configured),
missing-value skipping, snapshot + idempotent persistence, the
rate-limit guard seam, retry, and the missing-key raise.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

import workbench_api
from workbench_api.data.fred_loader import FREDMarketLoader
from workbench_api.data.market_context_common import RateLimitGuard
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.market_context import MarketContextRepository
from workbench_api.news.snapshot import NewsSnapshotWriter

FIXTURE_DIR = (
    Path(workbench_api.__file__).parent / "data" / "fixtures" / "market_context_responses"
)


def _fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return data


class _StubResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.request = httpx.Request("GET", "https://api.stlouisfed.org/x")

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        raise AssertionError("raise_for_status should not be hit in these tests")


class _StubClient:
    """Returns queued responses in order (last repeats)."""

    def __init__(self, responses: list[_StubResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, str]] = []

    def get(self, url: str, params: dict[str, str]) -> _StubResponse:  # noqa: ARG002
        self.calls.append(params)
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[idx]


class _CountingGuard:
    def __init__(self, raise_after: int | None = None) -> None:
        self.calls = 0
        self._raise_after = raise_after

    def check_and_increment(self) -> None:
        self.calls += 1
        if self._raise_after is not None and self.calls > self._raise_after:
            raise RuntimeError("daily quota exceeded")


@pytest.fixture
def ctx(initialised_db: str, tmp_path: Path) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    yield SimpleNamespace(
        session=session,
        repo=MarketContextRepository(session),
        writer=NewsSnapshotWriter(tmp_path / "market-context"),
    )
    session.close()


def _loader(
    payload: object, *, guard: RateLimitGuard | None = None, status: int = 200
) -> tuple[FREDMarketLoader, _StubClient]:
    client = _StubClient([_StubResponse(payload, status=status)])
    loader = FREDMarketLoader(
        api_key="test-key", client=client, sleep=lambda _s: None, guard=guard
    )
    return loader, client


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FRED_API_KEY missing"):
        FREDMarketLoader()


def test_fetch_series_parses_and_skips_missing() -> None:
    loader, _ = _loader(_fixture("fred-sample-DGS10.json"))
    payload, points = loader.fetch_series("DGS10")
    # 3 observations in fixture, one is "." → 2 parsed.
    assert [(p.obs_date, p.value) for p in points] == [
        (date(2026, 6, 3), 4.28),
        (date(2026, 6, 2), 4.25),
    ]
    assert "observations" in payload


def test_fetch_series_sends_expected_params() -> None:
    loader, client = _loader(_fixture("fred-sample-DGS10.json"))
    loader.fetch_series("DGS10", limit=10)
    params = client.calls[0]
    assert params["series_id"] == "DGS10"
    assert params["api_key"] == "test-key"
    assert params["file_type"] == "json"
    assert params["sort_order"] == "desc"
    assert params["limit"] == "10"


def test_fetch_and_store_writes_snapshot_and_persists(ctx: SimpleNamespace) -> None:
    loader, _ = _loader(_fixture("fred-sample-DGS10.json"))
    saved = loader.fetch_and_store(
        "DGS10", repo=ctx.repo, writer=ctx.writer, snapshot_date=date(2026, 6, 3)
    )
    assert saved == 2
    latest = ctx.repo.latest_by_series("DGS10")
    assert latest is not None
    assert latest.value == pytest.approx(4.28)
    assert latest.source == "fred"
    assert latest.snapshot_path == "fred/2026-06-03/DGS10.json"
    # Snapshot file actually written.
    assert (ctx.writer.root / "fred" / "2026-06-03" / "DGS10.json").is_file()


def test_fetch_and_store_is_idempotent(ctx: SimpleNamespace) -> None:
    loader, _ = _loader(_fixture("fred-sample-DGS10.json"))
    first = loader.fetch_and_store("DGS10", repo=ctx.repo, writer=ctx.writer)
    loader2, _ = _loader(_fixture("fred-sample-DGS10.json"))
    second = loader2.fetch_and_store("DGS10", repo=ctx.repo, writer=ctx.writer)
    assert first == 2
    assert second == 0  # same observations → all skipped
    assert ctx.repo.count() == 2


def test_guard_called_per_request() -> None:
    guard = _CountingGuard()
    loader, _ = _loader(_fixture("fred-sample-VIXCLS.json"), guard=guard)
    loader.fetch_series("VIXCLS")
    assert guard.calls == 1


def test_guard_can_halt_run() -> None:
    guard = _CountingGuard(raise_after=0)  # raise on the first call
    loader, _ = _loader(_fixture("fred-sample-VIXCLS.json"), guard=guard)
    with pytest.raises(RuntimeError, match="quota exceeded"):
        loader.fetch_series("VIXCLS")


def test_malformed_envelope_raises() -> None:
    loader, _ = _loader({"unexpected": "shape"})
    with pytest.raises(ValueError, match="missing 'observations'"):
        loader.fetch_series("DGS10")


def test_retry_on_500_then_success() -> None:
    client = _StubClient(
        [_StubResponse({}, status=500), _StubResponse(_fixture("fred-sample-VIXCLS.json"))]
    )
    loader = FREDMarketLoader(api_key="k", client=client, sleep=lambda _s: None)
    _payload, points = loader.fetch_series("VIXCLS")
    assert len(points) == 2
    assert len(client.calls) == 2  # one retry

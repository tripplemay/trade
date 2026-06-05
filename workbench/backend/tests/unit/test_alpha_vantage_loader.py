"""B035 F001 — Alpha Vantage market-context adapter (offline, stub httpx).

Pins the GLOBAL_QUOTE envelope (live-validated), the soft-error
detection (Note/Information → rate-limit raise), snapshot + idempotent
persistence, the rate-limit guard seam (the 25 req/day enforcement
point), and the missing-key raise.
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
from workbench_api.data.alpha_vantage_loader import AlphaVantageLoader
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
        self.request = httpx.Request("GET", "https://www.alphavantage.co/query")

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        raise AssertionError("raise_for_status should not be hit in these tests")


class _StubClient:
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
    payload: object, *, guard: RateLimitGuard | None = None
) -> tuple[AlphaVantageLoader, _StubClient]:
    client = _StubClient([_StubResponse(payload)])
    loader = AlphaVantageLoader(
        api_key="test-key", client=client, sleep=lambda _s: None, guard=guard
    )
    return loader, client


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ALPHAVANTAGE_API_KEY missing"):
        AlphaVantageLoader()


def test_fetch_series_parses_global_quote() -> None:
    loader, client = _loader(_fixture("alphavantage-sample-SPY.json"))
    payload, points = loader.fetch_series("SPY")
    assert len(points) == 1
    assert points[0].obs_date == date(2026, 6, 3)
    assert points[0].value == pytest.approx(580.50)
    assert client.calls[0]["function"] == "GLOBAL_QUOTE"
    assert client.calls[0]["symbol"] == "SPY"
    assert "Global Quote" in payload


def test_rate_limit_note_raises() -> None:
    loader, _ = _loader(
        {"Note": "Thank you for using Alpha Vantage! standard API rate limit is 25/day."}
    )
    with pytest.raises(ValueError, match="rate limit or bad symbol"):
        loader.fetch_series("SPY")


def test_information_field_raises() -> None:
    loader, _ = _loader({"Information": "invalid api call"})
    with pytest.raises(ValueError, match="rate limit or bad symbol"):
        loader.fetch_series("SPY")


def test_fetch_and_store_writes_snapshot_and_persists(ctx: SimpleNamespace) -> None:
    loader, _ = _loader(_fixture("alphavantage-sample-UUP.json"))
    saved = loader.fetch_and_store(
        "UUP", repo=ctx.repo, writer=ctx.writer, snapshot_date=date(2026, 6, 3)
    )
    assert saved == 1
    latest = ctx.repo.latest_by_series("UUP")
    assert latest is not None
    assert latest.value == pytest.approx(28.20)
    assert latest.source == "alpha_vantage"
    assert latest.snapshot_path == "alpha_vantage/2026-06-03/UUP.json"
    assert (ctx.writer.root / "alpha_vantage" / "2026-06-03" / "UUP.json").is_file()


def test_fetch_and_store_idempotent(ctx: SimpleNamespace) -> None:
    loader, _ = _loader(_fixture("alphavantage-sample-SPY.json"))
    first = loader.fetch_and_store("SPY", repo=ctx.repo, writer=ctx.writer)
    loader2, _ = _loader(_fixture("alphavantage-sample-SPY.json"))
    second = loader2.fetch_and_store("SPY", repo=ctx.repo, writer=ctx.writer)
    assert first == 1
    assert second == 0
    assert ctx.repo.count() == 1


def test_request_spacing_sleeps_before_each_request() -> None:
    """Alpha Vantage's free tier limits to 1 request/second; the loader
    must space requests so the daily 3-series fetch doesn't trip it
    (verified failing on the production VM 2026-06-05)."""

    slept: list[float] = []
    client = _StubClient([_StubResponse(_fixture("alphavantage-sample-SPY.json"))])
    loader = AlphaVantageLoader(
        api_key="k",
        client=client,
        sleep=lambda s: slept.append(s),
        request_spacing_seconds=2.0,
    )
    loader.fetch_series("SPY")
    assert 2.0 in slept


def test_request_spacing_can_be_disabled() -> None:
    slept: list[float] = []
    client = _StubClient([_StubResponse(_fixture("alphavantage-sample-SPY.json"))])
    loader = AlphaVantageLoader(
        api_key="k",
        client=client,
        sleep=lambda s: slept.append(s),
        request_spacing_seconds=0.0,
    )
    loader.fetch_series("SPY")
    assert slept == []  # no spacing, no retry → no sleeps


def test_guard_enforces_daily_quota() -> None:
    """The per-request guard is the 25 req/day enforcement seam — a guard
    that raises once its budget is hit halts the loader."""

    guard = _CountingGuard(raise_after=0)
    loader, _ = _loader(_fixture("alphavantage-sample-SPY.json"), guard=guard)
    with pytest.raises(RuntimeError, match="quota exceeded"):
        loader.fetch_series("SPY")

"""B033 F003 — news ingest CLI: argparse flags, resolvers, adapter
dispatch, and the end-to-end fetch loop driven through an injected
adapter factory (no real network / no real adapters).

The CLI is the production manual-trigger entrypoint
(``python -m workbench_api.news.cli fetch ...``); these tests pin the
flag contract spec §5 promises and verify ``fetch_main`` composes
``adapter → NewsSnapshotWriter → NewsRepository`` the way the F002 /
F003 adapter tests exercise it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from workbench_api.news.adapters.base import NewsItem
from workbench_api.news.cli import (
    DEFAULT_LOOKBACK_DAYS,
    REPO_ROOT,
    FetchSummary,
    _default_snapshot_root,
    build_adapters,
    fetch_main,
    parse_args,
    resolve_form_types,
    resolve_since,
    resolve_tickers,
)


def _news_item(*, source: str, source_id: str, ticker: str) -> NewsItem:
    return NewsItem(
        source=source,
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        title=f"{ticker} headline {source_id}",
        summary=None,
        ticker=ticker,
        form_type=None,
        published_at=datetime(2026, 5, 12, 9, 0, 0, tzinfo=UTC),
        raw_body=f"<doc>{source_id}</doc>".encode(),
        raw_ext="xml",
    )


class _FakeAdapter:
    """Records each fetch call + replays a fixed item list."""

    def __init__(self, source: str, items: list[NewsItem]) -> None:
        self.source = source
        self._items = items
        self.calls: list[tuple[str, datetime]] = []

    def fetch(self, *, ticker: str, since: datetime) -> Iterable[NewsItem]:
        self.calls.append((ticker, since))
        return list(self._items)


# --------------------------------------------------------------------------
# argparse contract
# --------------------------------------------------------------------------


def test_parse_args_fetch_defaults() -> None:
    args = parse_args(["fetch"])
    assert args.command == "fetch"
    assert args.source == "all"
    assert args.ticker is None
    assert args.since is None
    # Default form-types is the EDGAR four-form set, comma-joined.
    assert resolve_form_types(args.form_types) == frozenset(
        {"10-K", "10-Q", "8-K", "4"}
    )
    assert isinstance(args.snapshot_root, Path)


def test_parse_args_all_flags_parsed() -> None:
    args = parse_args(
        [
            "fetch",
            "--source",
            "edgar",
            "--ticker",
            "AAPL",
            "--since",
            "2026-01-15",
            "--form-types",
            "10-K,8-K",
            "--snapshot-root",
            "/tmp/news-snaps",
        ]
    )
    assert args.source == "edgar"
    assert args.ticker == "AAPL"
    assert args.since == "2026-01-15"
    assert args.form_types == "10-K,8-K"
    assert args.snapshot_root == Path("/tmp/news-snaps")


def test_parse_args_rejects_unknown_source() -> None:
    with pytest.raises(SystemExit):
        parse_args(["fetch", "--source", "reddit"])


# --------------------------------------------------------------------------
# resolvers
# --------------------------------------------------------------------------


def test_resolve_since_explicit_is_utc() -> None:
    resolved = resolve_since("2026-03-10")
    assert resolved == datetime(2026, 3, 10, tzinfo=UTC)


def test_resolve_since_default_is_lookback_window() -> None:
    resolved = resolve_since(None)
    assert resolved.tzinfo is not None
    expected = datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    # Allow a small clock delta between the two ``now`` reads.
    assert abs((resolved - expected).total_seconds()) < 60


def test_resolve_form_types_trims_and_dedups() -> None:
    assert resolve_form_types(" 10-K , 8-K ,10-K") == frozenset({"10-K", "8-K"})


def test_resolve_tickers_single() -> None:
    assert resolve_tickers("NVDA") == ("NVDA",)


def test_resolve_tickers_default_universe_includes_etfs() -> None:
    tickers = resolve_tickers(None)
    # B025 27 real + 4 master ETFs = 31.
    assert len(tickers) == 31
    for etf in ("SPY", "QQQ", "EFA", "EEM"):
        assert etf in tickers


# --------------------------------------------------------------------------
# adapter construction
# --------------------------------------------------------------------------


def test_build_adapters_all_builds_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEC_EDGAR_CONTACT_EMAIL", "cli-test@example.com")
    adapters = build_adapters(
        source_arg="all", form_types=frozenset({"10-K"})
    )
    assert set(adapters) == {"sec_edgar", "yahoo_rss"}


def test_build_adapters_yahoo_only_needs_no_secret() -> None:
    adapters = build_adapters(source_arg="yahoo", form_types=frozenset({"10-K"}))
    assert set(adapters) == {"yahoo_rss"}


def test_build_adapters_edgar_form_types_narrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--source=edgar --form-types 10-K`` constructs an EDGAR adapter
    restricted to the single form set (spec §8 dispatch assertion)."""

    monkeypatch.setenv("SEC_EDGAR_CONTACT_EMAIL", "cli-test@example.com")
    adapters = build_adapters(
        source_arg="edgar", form_types=frozenset({"10-K"})
    )
    assert set(adapters) == {"sec_edgar"}
    assert adapters["sec_edgar"].form_types == frozenset({"10-K"})  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# fetch_main dispatch loop
# --------------------------------------------------------------------------


def test_fetch_main_dispatch_all_runs_both_adapters(
    initialised_db: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """``--source=all`` fans the single ticker out across both adapters;
    each yielded item is snapshotted + persisted once."""

    edgar = _FakeAdapter(
        "sec_edgar", [_news_item(source="sec_edgar", source_id="acc-1", ticker="AAPL")]
    )
    yahoo = _FakeAdapter(
        "yahoo_rss", [_news_item(source="yahoo_rss", source_id="guid-1", ticker="AAPL")]
    )

    def factory(*, source_arg: str, form_types: frozenset[str]) -> dict[str, object]:
        assert source_arg == "all"
        return {"sec_edgar": edgar, "yahoo_rss": yahoo}

    args = parse_args(
        [
            "fetch",
            "--source",
            "all",
            "--ticker",
            "AAPL",
            "--since",
            "2026-01-01",
            "--snapshot-root",
            str(tmp_path / "snaps"),
        ]
    )
    summary = fetch_main(args, adapter_factory=factory)  # type: ignore[arg-type]
    assert isinstance(summary, FetchSummary)
    assert summary.saved == 2
    assert summary.skipped_existing == 0
    assert summary.errors == 0
    # Both adapters were invoked exactly once for the single ticker.
    assert edgar.calls == [("AAPL", datetime(2026, 1, 1, tzinfo=UTC))]
    assert yahoo.calls == [("AAPL", datetime(2026, 1, 1, tzinfo=UTC))]
    # Snapshots landed under the partitioned per-source path.
    snaps = list((tmp_path / "snaps").rglob("*.xml"))
    assert len(snaps) == 2


def test_fetch_main_second_run_is_idempotent(
    initialised_db: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """Re-running the same fetch persists nothing new — ``save_if_new``
    dedups on ``(source, source_id)``; the second summary reports the
    rows as skipped_existing."""

    yahoo = _FakeAdapter(
        "yahoo_rss",
        [
            _news_item(source="yahoo_rss", source_id="guid-1", ticker="AAPL"),
            _news_item(source="yahoo_rss", source_id="guid-2", ticker="AAPL"),
        ],
    )

    def factory(*, source_arg: str, form_types: frozenset[str]) -> dict[str, object]:
        return {"yahoo_rss": yahoo}

    args = parse_args(
        [
            "fetch",
            "--source",
            "yahoo",
            "--ticker",
            "AAPL",
            "--since",
            "2026-01-01",
            "--snapshot-root",
            str(tmp_path / "snaps"),
        ]
    )
    first = fetch_main(args, adapter_factory=factory)  # type: ignore[arg-type]
    assert (first.saved, first.skipped_existing) == (2, 0)
    second = fetch_main(args, adapter_factory=factory)  # type: ignore[arg-type]
    assert (second.saved, second.skipped_existing) == (0, 2)


def test_fetch_main_passes_resolved_form_types_to_factory(
    initialised_db: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """The ``--form-types`` flag must reach the adapter factory as a
    resolved frozenset (so EDGAR narrowing works end-to-end)."""

    captured: dict[str, object] = {}

    def factory(*, source_arg: str, form_types: frozenset[str]) -> dict[str, object]:
        captured["source_arg"] = source_arg
        captured["form_types"] = form_types
        return {}

    args = parse_args(
        [
            "fetch",
            "--source",
            "edgar",
            "--ticker",
            "AAPL",
            "--form-types",
            "10-K",
            "--snapshot-root",
            str(tmp_path / "snaps"),
        ]
    )
    fetch_main(args, adapter_factory=factory)  # type: ignore[arg-type]
    assert captured["source_arg"] == "edgar"
    assert captured["form_types"] == frozenset({"10-K"})


def test_fetch_main_creates_snapshot_dirs(
    initialised_db: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """The CLI mkdir -p's both per-source dirs at startup (so an empty
    universe run still leaves the expected directory layout)."""

    def factory(*, source_arg: str, form_types: frozenset[str]) -> dict[str, object]:
        return {}

    root = tmp_path / "snaps"
    args = parse_args(
        ["fetch", "--source", "all", "--snapshot-root", str(root)]
    )
    fetch_main(args, adapter_factory=factory)  # type: ignore[arg-type]
    assert (root / "sec_edgar").is_dir()
    assert (root / "yahoo_rss").is_dir()


def test_default_snapshot_root_honours_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B034 F001 — S1 closure: ``WORKBENCH_NEWS_SNAPSHOT_DIR`` overrides
    the repo-relative default so production persists snapshots outside the
    release tree (matches deploy.sh's persistent-data-root provisioning)."""

    persistent = tmp_path / "var" / "lib" / "workbench" / "data" / "snapshots" / "news"
    monkeypatch.setenv("WORKBENCH_NEWS_SNAPSHOT_DIR", str(persistent))
    assert _default_snapshot_root() == persistent


def test_default_snapshot_root_falls_back_to_repo_relative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the env var, the default stays repo-relative for local dev
    / tests — unchanged from the B033 behaviour."""

    monkeypatch.delenv("WORKBENCH_NEWS_SNAPSHOT_DIR", raising=False)
    assert _default_snapshot_root() == REPO_ROOT / "data" / "snapshots" / "news"

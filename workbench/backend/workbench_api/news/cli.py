"""B033 F003 — ``python -m workbench_api.news.cli fetch ...`` entrypoint.

Manual-trigger ingest CLI for the SEC EDGAR + Yahoo RSS adapters.
Production runs this manually after deploy (no cron / scheduler /
APScheduler — permanent product boundary **(q)**;
``tests/safety/test_news_no_scheduler.py`` enforces).

Flags:

``--source``       ``edgar`` / ``yahoo`` / ``all`` (default ``all``)
``--ticker``       single ticker; omit → full universe
``--since``        ``YYYY-MM-DD``; default 30 days ago
``--form-types``   comma-separated; default ``10-K,10-Q,8-K,4`` (edgar only)
``--snapshot-root`` override storage root; default
                    ``<repo>/data/snapshots/news``

The CLI composes ``Adapter → NewsSnapshotWriter → NewsRepository``
so the same code path the unit tests exercise (in
``tests/unit/test_news_adapter_edgar.py``) is what production runs.

Universe = B025 US Quality 27 real tickers + 4 master ETFs
(SPY / QQQ / EFA / EEM). Synthetic ``ZQ*`` tickers are skipped by
the EDGAR adapter (B029 fail-safe); they are silently dropped from
the Yahoo iteration because the RSS endpoint returns empty for them.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news.adapters.base import NewsAdapter, NewsItem
from workbench_api.news.adapters.sec_edgar import (
    DEFAULT_FORM_TYPES,
    SECEdgarNewsAdapter,
)
from workbench_api.news.adapters.yahoo_rss import (
    YahooRSSNewsAdapter,
    snapshot_filename,
)
from workbench_api.news.snapshot import NewsSnapshotWriter

logger = logging.getLogger(__name__)


# B033 spec §2 Universe — B025 US Quality 27 + 4 master ETFs.
def _default_universe() -> tuple[str, ...]:
    """B025 US Quality 27 real tickers + the 4 master ETFs.

    Sourced from the in-package ``equity_universe_tickers()`` — the same
    in-code ``_UNIVERSE_NAMES`` constant the news *request* path already
    uses (B034 F003) — **not** the repo-root ``scripts.universe_us_quality``
    (which pulls pandas at import and lives outside the deploy artifact).

    B038 wired this CLI into a production systemd timer (boundary (q)→(r));
    the deploy artifact ships only the ``workbench_api/`` package, so a
    runtime ``from scripts...`` import raised ``ModuleNotFoundError`` on the
    VM oneshot — v0.9.32 §12.10 deploy-artifact self-containment. The news
    ingest was previously manual-only (boundary (q)), which kept the
    repo-root import latent until the timer ran it in production. See
    docs/test-reports/B038-home-market-news-blocker-2026-06-06.md.
    """

    from workbench_api.news.ticker_match import equity_universe_tickers

    return equity_universe_tickers() + ("SPY", "QQQ", "EFA", "EEM")


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOOKBACK_DAYS = 30


def _default_snapshot_root() -> Path:
    """Resolve the snapshot storage root.

    B034 F001 closes the B033 signoff soft-watch **S1**: production
    persists news snapshots outside the repo tree (the VM provisions
    ``/var/lib/workbench/data/snapshots/news`` at deploy time), so the
    root must come from the ``WORKBENCH_NEWS_SNAPSHOT_DIR`` environment
    variable when set. It falls back to the repo-relative
    ``data/snapshots/news`` for local dev / tests where the env var is
    absent. This stays a CLI default only — the ingest CLI is still
    manual-trigger (no scheduler; permanent boundary **(q)**), so
    resolving the env var here does not make ingest run in production.
    """

    env_root = os.environ.get("WORKBENCH_NEWS_SNAPSHOT_DIR")
    if env_root:
        return Path(env_root)
    return REPO_ROOT / "data" / "snapshots" / "news"


DEFAULT_SNAPSHOT_ROOT = _default_snapshot_root()


@dataclass(frozen=True, slots=True)
class FetchSummary:
    """Aggregate result of one CLI fetch run."""

    saved: int
    skipped_existing: int
    errors: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build the argparse parser + parse the supplied (or sys) argv.

    Pulled into a module-level function so unit tests can drive the
    parser without invoking the full CLI machinery.
    """

    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.news.cli",
        description="B033 news ingest CLI — fetch SEC EDGAR + Yahoo RSS news.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser(
        "fetch",
        help="Fetch news for one source / one ticker (or full universe).",
    )
    fetch.add_argument(
        "--source",
        choices=("edgar", "yahoo", "all"),
        default="all",
        help="Which source to ingest (default: %(default)s).",
    )
    fetch.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Single ticker (default: full B025 + ETF universe).",
    )
    fetch.add_argument(
        "--since",
        type=str,
        default=None,
        help=(
            "ISO YYYY-MM-DD lower bound on published_at (default: "
            f"{DEFAULT_LOOKBACK_DAYS} days before today UTC)."
        ),
    )
    fetch.add_argument(
        "--form-types",
        type=str,
        default=",".join(sorted(DEFAULT_FORM_TYPES)),
        help=(
            "Comma-separated EDGAR form types (10-K,10-Q,8-K,4). "
            "Ignored when --source=yahoo. Default: %(default)s."
        ),
    )
    fetch.add_argument(
        "--snapshot-root",
        type=Path,
        default=DEFAULT_SNAPSHOT_ROOT,
        help="Root dir for raw body snapshots (default: %(default)s).",
    )
    return parser.parse_args(argv)


def resolve_since(since_arg: str | None) -> datetime:
    if since_arg is None:
        return datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    return datetime.fromisoformat(since_arg).replace(tzinfo=UTC)


def resolve_form_types(form_types_arg: str) -> frozenset[str]:
    return frozenset(part.strip() for part in form_types_arg.split(",") if part.strip())


def resolve_tickers(ticker_arg: str | None) -> tuple[str, ...]:
    if ticker_arg:
        return (ticker_arg,)
    return _default_universe()


def ensure_snapshot_dirs(root: Path, sources: Iterable[str]) -> None:
    for source in sources:
        (root / source).mkdir(parents=True, exist_ok=True)


def build_adapters(
    *, source_arg: str, form_types: frozenset[str]
) -> dict[str, NewsAdapter]:
    """Return ``{source_key: adapter}`` for the sources we'll iterate.

    Constructor wiring lives here so the CLI tests can call this
    function and inspect what got built without mocking
    :func:`fetch_main`'s end-to-end behaviour."""

    adapters: dict[str, NewsAdapter] = {}
    if source_arg in ("edgar", "all"):
        adapters["sec_edgar"] = SECEdgarNewsAdapter(form_types=form_types)
    if source_arg in ("yahoo", "all"):
        adapters["yahoo_rss"] = YahooRSSNewsAdapter()
    return adapters


def persist(
    *,
    item: NewsItem,
    writer: NewsSnapshotWriter,
    repo: NewsRepository,
) -> bool:
    """Write the snapshot + persist the row. ``True`` when newly inserted."""

    identifier = _snapshot_identifier(item)
    snap = writer.write(
        source=item.source,
        published_on=item.published_at.date(),
        identifier=identifier,
        body=item.raw_body,
        ext=item.raw_ext,
    )
    row = repo.save_if_new(
        item,
        snapshot_path=snap.relative_path,
        content_sha256=snap.content_sha256,
    )
    return row is not None


def _snapshot_identifier(item: NewsItem) -> str:
    """Pick a filesystem-safe identifier per source.

    SEC EDGAR accession numbers are already filesystem-safe
    (``0000320193-26-000020``). Yahoo RSS GUIDs may contain ``/``,
    ``?``, etc., so we hash them via :func:`snapshot_filename`.
    """

    if item.source == "yahoo_rss":
        return snapshot_filename(item.source_id)
    return item.source_id


AdapterFactory = Callable[..., dict[str, NewsAdapter]]


def fetch_main(
    args: argparse.Namespace,
    *,
    adapter_factory: AdapterFactory | None = None,
) -> FetchSummary:
    """Drive the fetch loop. Returns aggregated counts.

    ``adapter_factory`` is injectable for tests: pass a callable
    returning ``{source: adapter}`` to swap real adapters for fakes.
    Production callers omit the argument and the default factory
    builds real adapters from ``args``.
    """

    since = resolve_since(args.since)
    form_types = resolve_form_types(args.form_types)
    tickers = resolve_tickers(args.ticker)
    ensure_snapshot_dirs(args.snapshot_root, ("sec_edgar", "yahoo_rss"))
    if adapter_factory is None:
        adapters = build_adapters(source_arg=args.source, form_types=form_types)
    else:
        adapters = adapter_factory(
            source_arg=args.source, form_types=form_types
        )

    writer = NewsSnapshotWriter(args.snapshot_root)
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    saved = 0
    skipped = 0
    errors = 0
    try:
        repo = NewsRepository(session)
        for ticker in tickers:
            for source_key, adapter in adapters.items():
                try:
                    for item in adapter.fetch(ticker=ticker, since=since):
                        if persist(item=item, writer=writer, repo=repo):
                            saved += 1
                        else:
                            skipped += 1
                except KeyError as exc:
                    logger.info(
                        "news_cli_skip_unknown_ticker",
                        extra={
                            "ticker": ticker,
                            "source": source_key,
                            "reason": str(exc),
                        },
                    )
                except Exception:
                    errors += 1
                    logger.exception(
                        "news_cli_fetch_failure",
                        extra={"ticker": ticker, "source": source_key},
                    )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return FetchSummary(saved=saved, skipped_existing=skipped, errors=errors)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for ``python -m workbench_api.news.cli``."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "fetch":
        return 2
    summary = fetch_main(args)
    print(
        f"news ingest done — saved={summary.saved} "
        f"skipped_existing={summary.skipped_existing} "
        f"errors={summary.errors}"
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

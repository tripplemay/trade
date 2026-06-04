"""B035 F002 — ``python -m workbench_api.market.cli fetch`` entrypoint.

Daily read-only market-context ingest CLI for the FRED + Alpha Vantage
loaders. The production VM runs this once a day via a **systemd timer**
(``workbench/deploy/systemd/workbench-market-context.timer``) — not an
in-process scheduler, so the app stays stateless and no APScheduler
runtime dep is introduced.

Permanent product boundary **(r)** (B035 spec §3): this CLI does
**read-only data fetching only**. It composes ``loader → NewsSnapshotWriter
→ MarketContextRepository`` and never touches broker / order-ticket /
execution / recommendation / LLM code. ``tests/safety/test_market_scheduler_scope.py``
greps this module (and the systemd unit) to enforce that. News ingest
boundary **(q)** is unaffected — this timer serves market context only.

Flags:

``--source``         ``fred`` / ``alpha_vantage`` / ``all`` (default ``all``)
``--snapshot-root``  override storage root; default
                     ``WORKBENCH_MARKET_SNAPSHOT_DIR`` env, else
                     ``<repo>/data/snapshots/market-context``
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import sessionmaker

from workbench_api.data.alpha_vantage_loader import (
    ALPHA_VANTAGE_SERIES,
    AlphaVantageLoader,
)
from workbench_api.data.fred_loader import FRED_SERIES, FREDMarketLoader
from workbench_api.data.market_context_common import (
    SOURCE_ALPHA_VANTAGE,
    SOURCE_FRED,
)
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.market_context import MarketContextRepository
from workbench_api.news.snapshot import NewsSnapshotWriter

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
SERIES_BY_SOURCE: dict[str, tuple[str, ...]] = {
    SOURCE_FRED: FRED_SERIES,
    SOURCE_ALPHA_VANTAGE: ALPHA_VANTAGE_SERIES,
}


def _default_snapshot_root() -> Path:
    """Resolve the snapshot storage root.

    Honours ``WORKBENCH_MARKET_SNAPSHOT_DIR`` (the systemd service sets it
    to the persistent ``/var/lib/workbench/data/snapshots/market-context``
    so snapshots survive release swaps), falling back to a repo-relative
    path for local dev / tests. This is a CLI **write** path only — the
    timer does manual-trigger ingest, not an in-process scheduler
    (boundary (r))."""

    env_root = os.environ.get("WORKBENCH_MARKET_SNAPSHOT_DIR")
    if env_root:
        return Path(env_root)
    return REPO_ROOT / "data" / "snapshots" / "market-context"


@dataclass(frozen=True, slots=True)
class FetchSummary:
    """Aggregate result of one CLI fetch run."""

    saved: int
    errors: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.market.cli",
        description="B035 market-context ingest CLI — fetch FRED + Alpha Vantage.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="Fetch all market-context series.")
    fetch.add_argument(
        "--source",
        choices=(SOURCE_FRED, SOURCE_ALPHA_VANTAGE, "all"),
        default="all",
        help="Which source to ingest (default: %(default)s).",
    )
    fetch.add_argument(
        "--snapshot-root",
        type=Path,
        default=_default_snapshot_root(),
        help="Root dir for raw response snapshots (default: %(default)s).",
    )
    return parser.parse_args(argv)


class _Loader(Protocol):
    """Structural type both loaders satisfy (read-only fetch + persist)."""

    def fetch_and_store(
        self,
        series_id: str,
        *,
        repo: MarketContextRepository,
        writer: NewsSnapshotWriter,
    ) -> int: ...


def build_loaders(*, source_arg: str) -> dict[str, _Loader]:
    """Return ``{source: loader}`` for the sources we'll iterate.

    Constructor wiring lives here so the CLI tests can inspect / replace it
    via ``loader_factory`` without standing up real API keys."""

    loaders: dict[str, _Loader] = {}
    if source_arg in (SOURCE_FRED, "all"):
        loaders[SOURCE_FRED] = FREDMarketLoader()
    if source_arg in (SOURCE_ALPHA_VANTAGE, "all"):
        loaders[SOURCE_ALPHA_VANTAGE] = AlphaVantageLoader()
    return loaders


LoaderFactory = Callable[..., dict[str, _Loader]]


def ensure_snapshot_dirs(root: Path) -> None:
    for source in SERIES_BY_SOURCE:
        (root / source).mkdir(parents=True, exist_ok=True)


def fetch_main(
    args: argparse.Namespace,
    *,
    loader_factory: LoaderFactory | None = None,
) -> FetchSummary:
    """Drive the fetch loop. Returns aggregated counts.

    ``loader_factory`` is injectable for tests: pass a callable returning
    ``{source: loader}`` to swap real loaders for fakes. Production omits
    it and the default factory builds real loaders from the environment."""

    ensure_snapshot_dirs(args.snapshot_root)
    if loader_factory is None:
        loaders = build_loaders(source_arg=args.source)
    else:
        loaders = loader_factory(source_arg=args.source)

    writer = NewsSnapshotWriter(args.snapshot_root)
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    saved = 0
    errors = 0
    try:
        repo = MarketContextRepository(session)
        for source, loader in loaders.items():
            for series_id in SERIES_BY_SOURCE[source]:
                try:
                    saved += loader.fetch_and_store(
                        series_id, repo=repo, writer=writer
                    )
                except Exception:
                    errors += 1
                    logger.exception(
                        "market_cli_fetch_failure",
                        extra={"series_id": series_id, "source": source},
                    )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return FetchSummary(saved=saved, errors=errors)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "fetch":
        return 2
    summary = fetch_main(args)
    print(f"market-context ingest done — saved={summary.saved} errors={summary.errors}")
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

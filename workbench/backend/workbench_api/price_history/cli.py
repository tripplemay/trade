"""B048 F001 — ``python -m workbench_api.price_history.cli backfill`` entrypoint.

Reads the B045 unified prices CSV under ``--data-root`` and materialises
the deep daily close history into the ``price_history`` table (idempotent
by ``(symbol, obs_date)``). Can be run on the ``workbench-data-refresh``
cadence (after the refresh job writes the CSV) so the risk layer's
NAV-history reconstruction (B048 F003) always reads from the DB.

Boundary (r): read-only data job — it reads a CSV the refresh job wrote
and writes the DB; it never fetches from the network and never touches
broker / order-ticket / execution.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.price_history.backfill import BackfillSummary, run_backfill

DEFAULT_DATA_ROOT = "/var/lib/workbench/data"


def _default_data_root() -> Path:
    return Path(os.environ.get("WORKBENCH_DATA_ROOT", DEFAULT_DATA_ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.price_history.cli",
        description="B048 price-history backfill — unified prices CSV → price_history.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    backfill = sub.add_parser(
        "backfill", help="Materialise price_history from the unified prices CSV."
    )
    backfill.add_argument(
        "--data-root",
        type=Path,
        default=_default_data_root(),
        help="Root holding snapshots/prices/unified/prices_daily.csv (default: %(default)s).",
    )
    return parser.parse_args(argv)


def backfill_main(args: argparse.Namespace) -> BackfillSummary:
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        return run_backfill(session=session, data_root=args.data_root)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "backfill":
        return 2
    summary = backfill_main(args)
    print(
        "price-history backfill done — "
        f"rows_read={summary.rows_read} saved={summary.saved} "
        f"skipped_existing={summary.skipped_existing} "
        f"skipped_malformed={summary.skipped_malformed} symbols={summary.symbols}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

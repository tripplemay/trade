"""B045 F001 — ``python -m workbench_api.data_refresh.cli`` entrypoint.

The daily ``workbench-data-refresh`` systemd timer runs this. It fetches real
prices (Tiingo) + fundamentals (SEC EDGAR) for the Master universe and writes
the two unified CSVs under ``--data-root`` (the VM sets
``WORKBENCH_DATA_ROOT=/var/lib/workbench/data``). Boundary (r): read-only
market-data fetch — never broker / order-ticket / execution.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from workbench_api.data_refresh.refresh import RefreshSummary, run_refresh
from workbench_api.data_refresh.window import DataWindow, compute_data_window

# B047-OPS2 F001 (L4 deep backfill): ~5 years. risk_parity (120-day daily vol)
# + global_etf_momentum (~9-month) windows need history BEFORE the earliest
# usable signal date, so a 2-year window left only ~1.3 years of usable band and
# the default range fell off the front (open-the-box failure). 5 years gives the
# user a multi-year usable band and heals the B048 S1 degenerate-curve watch.
# Disk impact is small (~2.7 MB unified CSV at 5 years).
DEFAULT_LOOKBACK_DAYS = 1825
DEFAULT_DATA_ROOT = "/var/lib/workbench/data"

LoaderFactory = Callable[[], tuple[object, object]]


def _default_data_root() -> Path:
    return Path(os.environ.get("WORKBENCH_DATA_ROOT", DEFAULT_DATA_ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.data_refresh.cli",
        description="B045 real-data refresh — fetch Tiingo prices + SEC EDGAR fundamentals.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="Refresh the Master universe unified CSVs.")
    fetch.add_argument(
        "--data-root",
        type=Path,
        default=_default_data_root(),
        help="Root for snapshots/.../unified CSVs (default: %(default)s).",
    )
    fetch.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Calendar days of history to fetch (default: %(default)s).",
    )
    return parser.parse_args(argv)


def _build_loaders() -> tuple[object, object]:
    # Constructed here (not at import) so a dev rehearsal / test without the
    # secrets doesn't fail at import time. Keys come from the env file
    # (TIINGO_API_KEY / SEC_EDGAR_CONTACT_EMAIL).
    from workbench_api.data.sec_edgar_loader import SECEDGARFundamentalsLoader
    from workbench_api.data.tiingo_loader import TiingoSnapshotLoader

    return TiingoSnapshotLoader(), SECEDGARFundamentalsLoader()


def fetch_main(
    args: argparse.Namespace,
    *,
    loader_factory: LoaderFactory | None = None,
    today: date | None = None,
) -> RefreshSummary:
    run_date = today or datetime.now(UTC).date()
    from_date = run_date - timedelta(days=max(1, args.lookback_days))
    prices_loader, fundamentals_loader = (loader_factory or _build_loaders)()
    return run_refresh(
        data_root=args.data_root,
        from_date=from_date,
        to_date=run_date,
        prices_loader=prices_loader,  # type: ignore[arg-type]
        fundamentals_loader=fundamentals_loader,  # type: ignore[arg-type]
    )


def _persist_data_window(window: DataWindow) -> None:
    """Upsert the singleton coverage window the request path exposes (L2).

    Imported lazily so a CSV-only rehearsal / test never needs the DB stack."""

    from sqlalchemy.orm import sessionmaker

    from workbench_api.db.engine import get_engine
    from workbench_api.db.repositories.backtest_data_window import (
        BacktestDataWindowRepository,
    )

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        BacktestDataWindowRepository(session).upsert_window(
            data_start=window.data_start,
            data_end=window.data_end,
            first_usable_signal_date=window.first_usable_signal_date,
        )
        session.commit()
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "fetch":
        return 2
    summary = fetch_main(args)
    print(
        "data refresh done — "
        f"price_symbols={summary.price_symbols} price_rows={summary.price_rows} "
        f"fundamental_symbols={summary.fundamental_symbols} "
        f"fundamental_rows={summary.fundamental_rows} errors={summary.errors}"
    )

    # B047-OPS2 F001 (L2) — record the real coverage window so the request-path
    # GET /api/backtests/data-range can expose it (and the frontend can pick a
    # valid default range + clamp the picker). The CSV is the primary deliverable
    # and is already written above; the DB write is secondary, so it runs after.
    #
    # §12.11.1 entry-level env guard: this entry now WRITES the prod DB, so guard
    # before the write — a bare hand-run without WORKBENCH_DB_URL must hard-fail
    # loudly (::error::, non-zero) rather than silently write the window to the
    # dev scratch DB while the API reads prod.
    from workbench_api.db.require_production_db import (
        ScratchDatabaseError,
        require_production_db,
    )

    window = compute_data_window(Path(summary.prices_path))
    if window is not None:
        try:
            require_production_db(entrypoint="data-refresh")
        except ScratchDatabaseError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        _persist_data_window(window)
        print(
            "data window — "
            f"data_start={window.data_start.isoformat()} "
            f"data_end={window.data_end.isoformat()} "
            f"first_usable_signal_date={window.first_usable_signal_date.isoformat()}"
        )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

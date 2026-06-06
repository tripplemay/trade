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

# ~2 years so risk_parity (120-day daily vol) + global_etf_momentum (9-month)
# windows have enough history on the latest signal date.
DEFAULT_LOOKBACK_DAYS = 730
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
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

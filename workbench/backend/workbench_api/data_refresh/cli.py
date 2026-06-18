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
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from workbench_api.data_refresh.cn_universe import (
    DEFAULT_TOP_N,
    CnUniverseSummary,
    MarketCapLoader,
    build_cn_universe,
    quarterly_rebalance_dates,
)
from workbench_api.data_refresh.fx_refresh import run_fx_refresh
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

LoaderFactory = Callable[[], tuple[object, object, object, object]]


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
    # B065 F001 — A-share point-in-time universe build (off the same fetch).
    fetch.add_argument(
        "--no-cn-universe",
        action="store_true",
        help="Skip the B065 A-share point-in-time universe build.",
    )
    fetch.add_argument(
        "--cn-universe-top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help="Members per rebalance in the A-share PIT universe (default: %(default)s).",
    )
    fetch.add_argument(
        "--cn-universe-max-superset",
        type=int,
        default=300,
        help="Cap on the discovered/seed A-share fetch superset (default: %(default)s).",
    )
    return parser.parse_args(argv)


def _build_loaders() -> tuple[object, object, object, object]:
    # Constructed here (not at import) so a dev rehearsal / test without the
    # secrets doesn't fail at import time. Keys come from the env file
    # (TIINGO_API_KEY / SEC_EDGAR_CONTACT_EMAIL / FRED_API_KEY).
    from workbench_api.data.sec_edgar_loader import SECEDGARFundamentalsLoader
    from workbench_api.data.tiingo_loader import TiingoSnapshotLoader
    from workbench_api.data_refresh.cn_hk_prices import CnHkPricesLoader
    from workbench_api.data_refresh.fx_refresh import FredFxLoader

    # CnHkPricesLoader lazy-imports akshare per fetch (B062 F002); FredFxLoader
    # lazy-builds the FRED client per fetch (B063 F001). Both cheap + key-free
    # to construct.
    return (
        TiingoSnapshotLoader(),
        SECEDGARFundamentalsLoader(),
        CnHkPricesLoader(),
        FredFxLoader(),
    )


def fetch_main(
    args: argparse.Namespace,
    *,
    loader_factory: LoaderFactory | None = None,
    today: date | None = None,
    cn_universe_loader: MarketCapLoader | None = None,
    superset_provider: Callable[[], Sequence[str]] | None = None,
) -> RefreshSummary:
    run_date = today or datetime.now(UTC).date()
    from_date = run_date - timedelta(days=max(1, args.lookback_days))
    prices_loader, fundamentals_loader, cn_hk_prices_loader, fx_loader = (
        loader_factory or _build_loaders
    )()

    # B065 F001 — resolve the A-share fetch superset BEFORE the refresh so its
    # members' prices are fetched (the universe builder needs them for turnover).
    # ``cn_universe_loader is None`` (the default / tests) keeps the US+CN_HK
    # behaviour unchanged.
    build_universe = cn_universe_loader is not None and not getattr(args, "no_cn_universe", False)
    superset: Sequence[str] = (
        (superset_provider() if superset_provider is not None else ()) if build_universe else ()
    )

    summary = run_refresh(
        data_root=args.data_root,
        from_date=from_date,
        to_date=run_date,
        prices_loader=prices_loader,  # type: ignore[arg-type]
        fundamentals_loader=fundamentals_loader,  # type: ignore[arg-type]
        cn_hk_prices_loader=cn_hk_prices_loader,  # type: ignore[arg-type]
        cn_extra_price_symbols=superset or None,
    )
    # B063 F001 — also refresh the FX rates CSV (FRED CNY/USD + HKD/USD) the
    # backtest reads for USD conversion. Best-effort per series (logged inside).
    run_fx_refresh(data_root=args.data_root, fx_loader=fx_loader)  # type: ignore[arg-type]

    # B065 F001 — build the A-share point-in-time universe membership artifact
    # from the prices CSV just written + historical market caps. Best-effort: a
    # universe failure never fails the US/CN_HK refresh.
    if build_universe and superset and cn_universe_loader is not None:
        _build_cn_universe(
            args,
            prices_path=Path(summary.prices_path),
            marketcap_loader=cn_universe_loader,
            superset=superset,
            from_date=from_date,
            to_date=run_date,
        )
    return summary


def _build_cn_universe(
    args: argparse.Namespace,
    *,
    prices_path: Path,
    marketcap_loader: MarketCapLoader,
    superset: Sequence[str],
    from_date: date,
    to_date: date,
) -> CnUniverseSummary | None:
    rebalances = quarterly_rebalance_dates(from_date, to_date)
    try:
        return build_cn_universe(
            data_root=args.data_root,
            prices_path=prices_path,
            marketcap_loader=marketcap_loader,
            superset=superset,
            rebalance_dates=rebalances,
            from_date=from_date,
            to_date=to_date,
            top_n=args.cn_universe_top_n,
        )
    except Exception:  # noqa: BLE001 — best-effort; never fail the US refresh
        logging.getLogger(__name__).exception("cn_universe_build_failed")
        return None


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

    # B065 F001 — wire the A-share PIT universe build into the production fetch.
    # The loader (akshare stock_value_em) + best-effort superset discovery are
    # lazy/key-free; ``--no-cn-universe`` disables it. Tests call fetch_main with
    # cn_universe_loader=None, so this only runs in the real job.
    cn_universe_loader: MarketCapLoader | None = None
    superset_provider: Callable[[], Sequence[str]] | None = None
    if not args.no_cn_universe:
        from workbench_api.data_refresh.cn_marketcap import (
            CnMarketCapLoader,
            discover_ashare_superset,
        )

        cn_universe_loader = CnMarketCapLoader()
        superset_provider = lambda: discover_ashare_superset(  # noqa: E731
            top_n=args.cn_universe_max_superset
        )[0]

    summary = fetch_main(
        args,
        cn_universe_loader=cn_universe_loader,
        superset_provider=superset_provider,
    )
    print(
        "data refresh done — "
        f"price_symbols={summary.price_symbols} price_rows={summary.price_rows} "
        f"fundamental_symbols={summary.fundamental_symbols} "
        f"fundamental_rows={summary.fundamental_rows} "
        f"cn_universe_price_rows={summary.cn_universe_price_rows} errors={summary.errors}"
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

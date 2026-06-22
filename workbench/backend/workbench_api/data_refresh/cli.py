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
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from workbench_api.cli_clock import add_as_of_argument
from workbench_api.data_refresh.cn_universe import (
    CnUniverseSummary,
    MarketCapLoader,
    build_cn_universe,
    quarterly_rebalance_dates,
)
from workbench_api.data_refresh.fx_refresh import run_fx_refresh
from workbench_api.data_refresh.refresh import (
    RefreshSummary,
    _CnFundamentalsLoader,
    run_refresh,
)
from workbench_api.data_refresh.window import DataWindow, compute_data_window

# B047-OPS2 F001 (L4 deep backfill): ~5 years. risk_parity (120-day daily vol)
# + global_etf_momentum (~9-month) windows need history BEFORE the earliest
# usable signal date, so a 2-year window left only ~1.3 years of usable band and
# the default range fell off the front (open-the-box failure). 5 years gives the
# user a multi-year usable band and heals the B048 S1 degenerate-curve watch.
# Disk impact is small (~2.7 MB unified CSV at 5 years).
DEFAULT_LOOKBACK_DAYS = 1825
DEFAULT_DATA_ROOT = "/var/lib/workbench/data"

# B075 F001 — the wide A-share universe target N. The batch goal is top ~1500
# liquid (市值 + 成交额, ST excluded). It is *feasibility-gated*: the VM probe
# (scripts/research/b075_wide_universe_feasibility_probe.py) measured the prod VM
# can refresh this N daily (prices ≈ 39min serial via the §23 VM-reachable sina
# bulk endpoint; GO at N=1500, headroom to ~3400). If a future re-measure shows
# 1500 no longer refreshable, lower this + the systemd unit args together (honest
# fallback, never a silent cap — B070 precedent). The universe build (historical
# market cap) + CAS fundamentals are far heavier (~2h each at this N) and so run
# on a separate LOW-FREQUENCY timer, decoupled from the daily price refresh.
WIDE_UNIVERSE_TARGET_N = 1500

# B075 F001 — over a ~1500-name universe a tail of per-symbol fetch failures
# (delisted / suspended / newly-listed names) is normal and must NOT fail the
# timer (partial-failure 优雅, 不炸整轮 — the survivors are written). The wide
# A-share blocks fail the job only when the failure RATE crosses this floor, which
# signals a real outage (e.g. the bulk host down → most/all names fail) rather
# than the expected long tail. US / CN_HK proxy failures stay strict (rate 0).
WIDE_CN_MAX_FAILURE_RATE = 0.2

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
        default=WIDE_UNIVERSE_TARGET_N,
        help="Members per rebalance in the A-share PIT universe (default: %(default)s).",
    )
    fetch.add_argument(
        "--cn-universe-max-superset",
        type=int,
        default=WIDE_UNIVERSE_TARGET_N,
        help="Cap on the discovered/seed A-share fetch superset (default: %(default)s).",
    )
    # B075 F001 — opt-in the §23 VM-reachable sina bulk endpoint so discovery
    # widens to the full liquid market (top-N) instead of degrading to the curated
    # ~43-name seed. Default OFF keeps the pre-B075 behaviour byte-identical (the
    # eastmoney push host fails on the VM → seed), so this must be passed
    # explicitly by the production wide-universe timers (F002).
    fetch.add_argument(
        "--cn-universe-sina-fallback",
        action="store_true",
        help="Enable the sina bulk-spot discovery fallback (wide universe).",
    )
    # B075 F001 — decouple the two HEAVY, low-churn cost centres from the daily
    # price refresh. The historical-market-cap universe build (~2h at N=1500) only
    # matters at quarterly rebalances, and CAS fundamentals change quarterly, so
    # the daily timer skips both (--no-cn-universe-build --no-cn-fundamentals) and
    # a separate weekly timer runs them. Default OFF = both run (pre-B075 + the
    # weekly job's behaviour).
    fetch.add_argument(
        "--no-cn-universe-build",
        action="store_true",
        help="Skip the historical-mcap PIT universe build (prices still fetched).",
    )
    fetch.add_argument(
        "--no-cn-fundamentals",
        action="store_true",
        help="Skip the A-share CAS fundamentals fetch (decoupled to a low-freq job).",
    )
    add_as_of_argument(fetch)
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
    cn_fundamentals_loader: _CnFundamentalsLoader | None = None,
    cn_benchmark_loader: object | None = None,
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
    want_cn = cn_universe_loader is not None and not getattr(args, "no_cn_universe", False)
    superset: Sequence[str] = (
        (superset_provider() if superset_provider is not None else ()) if want_cn else ()
    )
    # B075 F001 — the two heavy cost centres are independently switchable so the
    # daily price timer can stay light (~39min) while a weekly timer carries the
    # historical-mcap universe build + CAS fundamentals (~2h each). Default-on
    # (flag absent) preserves the pre-B075 single-job behaviour.
    build_universe = want_cn and not getattr(args, "no_cn_universe_build", False)
    fetch_cn_fundamentals = (
        want_cn
        and cn_fundamentals_loader is not None
        and not getattr(args, "no_cn_fundamentals", False)
    )

    summary = run_refresh(
        data_root=args.data_root,
        from_date=from_date,
        to_date=run_date,
        prices_loader=prices_loader,  # type: ignore[arg-type]
        fundamentals_loader=fundamentals_loader,  # type: ignore[arg-type]
        cn_hk_prices_loader=cn_hk_prices_loader,  # type: ignore[arg-type]
        # Wide A-share prices are the daily 命门 — fetched whenever the CN path is
        # on, even when the universe build / fundamentals are skipped for the day.
        cn_extra_price_symbols=superset or None,
        # B065 F002 — CAS fundamentals for the same A-share superset (appended
        # after the US SEC rows). B075 F001: decoupled to a low-freq job, so the
        # loader is passed only when fundamentals are wanted this run.
        cn_fundamentals_loader=cn_fundamentals_loader if fetch_cn_fundamentals else None,
        cn_fundamentals_symbols=superset if fetch_cn_fundamentals else None,
    )
    # B063 F001 — also refresh the FX rates CSV (FRED CNY/USD + HKD/USD) the
    # backtest reads for USD conversion. Best-effort per series (logged inside).
    run_fx_refresh(data_root=args.data_root, fx_loader=fx_loader)  # type: ignore[arg-type]

    # B066 F003 — refresh the CSI 300 (沪深300) benchmark CSV the CN attack
    # comparison report reads. Best-effort (logged inside): a fetch failure leaves
    # the file unwritten → the report degrades to "benchmark unavailable". Only the
    # real job injects the loader (tests pass None).
    if cn_benchmark_loader is not None:
        from workbench_api.data_refresh.cn_benchmark import run_cn_benchmark_refresh

        run_cn_benchmark_refresh(
            data_root=args.data_root,
            loader=cn_benchmark_loader,  # type: ignore[arg-type]
        )

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


@dataclass(frozen=True, slots=True)
class ExitDecision:
    """B075 F001 — the refresh job's exit verdict with partial-failure tolerance."""

    exit_code: int
    core_errors: int  # US / CN_HK ("core") per-symbol failures — strict
    wide_errors: int  # wide A-share price + CAS fundamentals failures — tolerated
    wide_attempted: int
    wide_failure_rate: float
    wide_block_failed: bool  # wide rate crossed the floor (a real outage)


def resolve_exit_decision(summary: RefreshSummary) -> ExitDecision:
    """Job exit code: strict on core errors, tolerant of a bounded wide-block tail.

    A handful of per-symbol failures over the ~1500-name wide A-share universe
    (delisted / suspended / newly-listed) is expected and must not fail the timer
    (partial-failure 优雅, 不炸整轮 — the survivors are written). US / CN_HK proxy
    failures stay strict. The wide block fails the job only when its failure RATE
    crosses :data:`WIDE_CN_MAX_FAILURE_RATE`, which signals a real outage (e.g. the
    bulk host down → most names fail) rather than the expected long tail."""

    wide_attempted = summary.cn_universe_price_symbols + summary.cn_fundamental_symbols
    wide_errors = summary.cn_universe_price_errors + summary.cn_fundamental_errors
    core_errors = summary.errors - wide_errors
    wide_failure_rate = (wide_errors / wide_attempted) if wide_attempted else 0.0
    wide_block_failed = wide_failure_rate > WIDE_CN_MAX_FAILURE_RATE
    exit_code = 0 if (core_errors == 0 and not wide_block_failed) else 1
    return ExitDecision(
        exit_code=exit_code,
        core_errors=core_errors,
        wide_errors=wide_errors,
        wide_attempted=wide_attempted,
        wide_failure_rate=wide_failure_rate,
        wide_block_failed=wide_block_failed,
    )


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
    cn_fundamentals_loader: _CnFundamentalsLoader | None = None
    cn_benchmark_loader: object | None = None
    if not args.no_cn_universe:
        from workbench_api.data_refresh.cn_benchmark import AkshareCsiLoader
        from workbench_api.data_refresh.cn_fundamentals import CnFundamentalsLoader
        from workbench_api.data_refresh.cn_marketcap import (
            CnMarketCapLoader,
            discover_ashare_superset,
        )

        cn_universe_loader = CnMarketCapLoader()
        # B075 F001 — ungate wide discovery: pass the sina-fallback flag through so
        # the production timers can widen to the full liquid market (the §23
        # VM-reachable bulk endpoint). Absent the flag this stays the curated seed.
        superset_provider = lambda: discover_ashare_superset(  # noqa: E731
            top_n=args.cn_universe_max_superset,
            allow_sina_fallback=args.cn_universe_sina_fallback,
        )[0]
        # B065 F002 — CAS fundamentals for the superset → fundamentals.csv.
        cn_fundamentals_loader = CnFundamentalsLoader()
        # B066 F003 — CSI 300 benchmark for the CN attack comparison report.
        cn_benchmark_loader = AkshareCsiLoader()

    summary = fetch_main(
        args,
        # B072 F003 — --as-of pins the refresh window's run date; omitted → today (UTC).
        today=args.as_of,
        cn_universe_loader=cn_universe_loader,
        superset_provider=superset_provider,
        cn_fundamentals_loader=cn_fundamentals_loader,
        cn_benchmark_loader=cn_benchmark_loader,
    )
    print(
        "data refresh done — "
        f"price_symbols={summary.price_symbols} price_rows={summary.price_rows} "
        f"fundamental_symbols={summary.fundamental_symbols} "
        f"fundamental_rows={summary.fundamental_rows} "
        f"cn_universe_price_rows={summary.cn_universe_price_rows} "
        f"cn_fundamental_rows={summary.cn_fundamental_rows} errors={summary.errors}"
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

    # B075 F001 — partial-failure 优雅: the wide A-share blocks (price extension +
    # CAS fundamentals) tolerate a bounded tail of per-symbol failures; only
    # US / CN_HK ("core") failures, or a wide failure RATE over the floor (a real
    # outage), fail the job. The survivors are always written (不炸整轮).
    decision = resolve_exit_decision(summary)
    if decision.wide_errors:
        logging.getLogger(__name__).warning(
            "data_refresh_wide_cn_partial_failure: %d/%d wide A-share fetches failed "
            "(rate %.1f%%, floor %.0f%%) — survivors written; %s",
            decision.wide_errors,
            decision.wide_attempted,
            decision.wide_failure_rate * 100,
            WIDE_CN_MAX_FAILURE_RATE * 100,
            "FAILING the job (rate over floor)"
            if decision.wide_block_failed
            else "tolerated (不炸整轮)",
        )
    print(
        f"exit policy — core_errors={decision.core_errors} "
        f"wide_errors={decision.wide_errors}/{decision.wide_attempted} "
        f"wide_rate={decision.wide_failure_rate:.3f} floor={WIDE_CN_MAX_FAILURE_RATE}"
    )
    return decision.exit_code


if __name__ == "__main__":
    sys.exit(main())

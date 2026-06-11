"""B056 F001 — ``python -m workbench_api.paper.cli activate ...``.

Off-request-path activation entrypoint: create a paper account for a strategy
with virtual capital and build its first book from the strategy's current
target. Manual-trigger (no scheduler); production / F004 L2 runs it once per
strategy to start the forward simulation. The daily MTM job (F002) then marks
it to market and rebalances when the strategy publishes a new allocation.

Reads the already-stored strategy target + price marks — never imports ``trade``
or contacts a broker.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.paper.service import (
    DEFAULT_BASE_CURRENCY,
    DEFAULT_FEE_BPS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_SLIPPAGE_BPS,
    PaperAccountExistsError,
    activate_paper_account,
)
from workbench_api.paper.targets import MASTER_STRATEGY_ID

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.paper.cli",
        description="B056 paper-trading activation CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    activate = sub.add_parser("activate", help="Activate a paper account.")
    activate.add_argument(
        "--strategy", type=str, default=MASTER_STRATEGY_ID,
        help="strategy_id to forward-simulate (default: %(default)s).",
    )
    activate.add_argument(
        "--capital", type=float, default=DEFAULT_INITIAL_CAPITAL,
        help="Virtual initial capital (default: %(default)s).",
    )
    activate.add_argument(
        "--base-currency", type=str, default=DEFAULT_BASE_CURRENCY,
        help="Base currency (default: %(default)s).",
    )
    activate.add_argument(
        "--fee-bps", type=float, default=DEFAULT_FEE_BPS,
        help="Commission cost in bps of traded notional (default: %(default)s).",
    )
    activate.add_argument(
        "--slippage-bps", type=float, default=DEFAULT_SLIPPAGE_BPS,
        help="Slippage cost in bps of traded notional (default: %(default)s).",
    )
    activate.add_argument(
        "--on-date", type=str, default=None,
        help="Activation date ISO YYYY-MM-DD (default: today UTC).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)
    if args.command != "activate":
        return 2

    now = datetime.now(UTC)
    on_date = (
        date.fromisoformat(args.on_date) if args.on_date else now.date()
    )
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        account, plan = activate_paper_account(
            session,
            strategy_id=args.strategy,
            on_date=on_date,
            now=now,
            initial_capital=args.capital,
            base_currency=args.base_currency,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
        )
        session.commit()
    except PaperAccountExistsError:
        print(f"paper account already exists for strategy {args.strategy!r}")
        session.rollback()
        return 1
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if plan is None:
        print(
            f"activated paper account for {args.strategy!r} (all cash — no "
            "strategy target available yet; first build on next daily job)"
        )
    else:
        print(
            f"activated paper account for {args.strategy!r}: "
            f"{len(plan.positions)} positions, cost={plan.cost:.2f}, "
            f"skipped={list(plan.skipped_symbols)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

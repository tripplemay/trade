"""B072 F001 — golden → DB seed for the full-stack e2e / CI.

Pushes the committed golden real-data fixture (``data/fixtures/golden/``) into
the workbench DB so the full-stack CI (uvicorn + backtest worker + Playwright)
and the e2e trading loop (B072 F002) run against deterministic, real-shaped
data. Four tables, all seeded from golden:

* ``price_snapshot``         — the latest two golden closes per symbol so the
  mark-to-market provider (``DbPriceProvider``) can value held + target
  positions (a symbol needs two closes to be marked).
* ``recommendation_snapshot`` — the real Master Portfolio target scored on
  golden via ``score_master_target(fixture_dir=...)`` → ``run_precompute`` (the
  same real scoring the daily timer runs, deterministic, ``data_source=fixture``).
* ``account_snapshot``       — a deterministic closed-loop account (cash + two
  golden holdings) so /recommendations + /execution/position-diff show a
  non-empty, marked diff (and the F002 reconcile never overdraws).
* ``investment_report``      — reuses :func:`seed_e2e_reports.seed` so /reports
  has a row (the b040 metrics-card e2e depends on its slug).

Determinism: the same golden CSVs always produce the same DB *content* — price
rows are insert-if-new, the recommendation batch is delete-then-insert, the
account + report are upserts by a fixed key. Row UUIDs differ across runs; the
business content does not (asserted by ``tests/acceptance/test_b072_golden_
fullstack_seed.py``).

Test-only: never wired into ``deploy.sh`` or any systemd unit. Run after
``alembic upgrade head``::

    WORKBENCH_DB_URL=sqlite:///./e2e-workbench.db python scripts/seed_golden_e2e.py
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import seed_e2e_reports
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import (
    DEFAULT_STRATEGY_ID,
    AccountSnapshot,
)
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.recommendations.precompute import run_precompute, score_master_target

# scripts/ → backend/ → workbench/ → repo root (parents[3]).
GOLDEN_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "golden"
_PRICES_CSV = GOLDEN_DIR / "prices_daily.csv"

# Deterministic stamps (mirror seed_e2e_reports) so a re-run is content-stable.
FIXED_COMPUTED_AT = datetime(2026, 6, 1, 4, 0, tzinfo=UTC)
# Naive UTC, matching the account_snapshot model + the UI write path
# (services.execution.update_account uses datetime.now(UTC).replace(tzinfo=None)).
ACCOUNT_SNAPSHOT_AT = datetime(2026, 6, 1, 0, 0, 0)
ACCOUNT_ID = "snap-golden-e2e"
ACCOUNT_CASH = Decimal("1000000")
# A small initial holding of two golden symbols: the position-diff then shows a
# rebalance on the held names and many buys on the target names not yet held.
# Ample cash so the F002 reconcile applies its buy fills without overdrawing.
HELD_SHARES: dict[str, float] = {"SPY": 10.0, "AAPL": 5.0}
PRICE_SOURCE = "golden"


def latest_two_closes() -> dict[str, list[tuple[date, float]]]:
    """Return ``{ticker: [(obs_date, close), ...]}`` with the two most recent
    golden closes per ticker (oldest-first), so ``DbPriceProvider`` has a latest
    + prior close to mark each symbol with. Parses the golden CSV exactly once."""

    by_ticker: dict[str, list[tuple[date, float]]] = {}
    with _PRICES_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_ticker.setdefault(row["ticker"], []).append(
                (date.fromisoformat(row["date"]), float(row["close"]))
            )
    return {
        ticker: sorted(rows, key=lambda r: r[0])[-2:]
        for ticker, rows in by_ticker.items()
    }


def seed_price_snapshots(
    session: Session, closes: dict[str, list[tuple[date, float]]]
) -> int:
    """Seed the latest two golden closes for every golden symbol. Returns the
    number of rows newly inserted (0 on an idempotent re-run)."""

    repo = PriceSnapshotRepository(session)
    written = 0
    for ticker, rows in closes.items():
        for obs_date, close in rows:
            inserted = repo.save_if_new(
                symbol=ticker,
                obs_date=obs_date,
                close=close,
                source=PRICE_SOURCE,
                fetched_at=FIXED_COMPUTED_AT,
            )
            if inserted is not None:
                written += 1
    return written


def seed_recommendation_snapshot(session: Session) -> int:
    """Score the real Master Portfolio target on golden and persist it
    (deterministic, ``data_source=fixture``). Returns the row count."""

    summary = run_precompute(
        session,
        score_fn=lambda: score_master_target(fixture_dir=GOLDEN_DIR),
        computed_at=FIXED_COMPUTED_AT,
        explainer=None,  # deterministic placeholder rationale; no LLM/network.
    )
    if summary.error is not None or summary.saved == 0:
        raise RuntimeError(
            f"golden recommendation precompute produced no rows: error={summary.error!r}"
        )
    return summary.saved


def seed_account_snapshot(
    session: Session, closes: dict[str, list[tuple[date, float]]]
) -> AccountSnapshot:
    """Seed the deterministic closed-loop account (cash + two golden holdings)."""

    positions: list[dict[str, object]] = []
    for symbol, shares in HELD_SHARES.items():
        rows = closes.get(symbol)
        if not rows:
            raise RuntimeError(f"golden fixture has no price for held symbol {symbol}")
        positions.append(
            {"symbol": symbol, "shares": shares, "avg_cost": round(rows[-1][1], 4)}
        )
    row = AccountSnapshot(
        id=ACCOUNT_ID,
        snapshot_at=ACCOUNT_SNAPSHOT_AT,
        strategy_id=DEFAULT_STRATEGY_ID,
        cash=ACCOUNT_CASH,
        base_currency="USD",
        positions=positions,
        source="ui_edit",
        created_at=ACCOUNT_SNAPSHOT_AT,
    )
    AccountSnapshotRepository(session).upsert(row)
    return row


def seed_all(session: Session) -> dict[str, int]:
    """Seed all four golden tables. Caller commits (``main`` / the test)."""

    closes = latest_two_closes()
    prices = seed_price_snapshots(session, closes)
    recommendations = seed_recommendation_snapshot(session)
    seed_account_snapshot(session, closes)
    seed_e2e_reports.seed(session)  # investment_report (b040 metrics-card slug).
    return {
        "price_snapshots": prices,
        "recommendations": recommendations,
        "accounts": 1,
        "reports": 1,
    }


def main() -> None:
    with Session(bind=get_engine(), future=True) as session:
        counts = seed_all(session)
        session.commit()
    print(
        "seeded golden e2e: "
        f"price_snapshots={counts['price_snapshots']} "
        f"recommendations={counts['recommendations']} "
        f"accounts={counts['accounts']} reports={counts['reports']}"
    )


if __name__ == "__main__":
    main()

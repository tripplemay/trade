"""B047 F004 — seed one canonical investment report for the frontend e2e DB.

The Reports page is now DB-backed (``kind='investment'``): it reads the
``investment_report`` rows written by the canonical job, NOT the filesystem
``docs/test-reports/`` dev sign-offs. The frontend Playwright suite boots a
fresh SQLite DB (``alembic upgrade head``) with no data, so ``/reports`` and
``/reports/[slug]`` would be empty and the b040 "metrics card above markdown"
e2e would 404.

Running the real canonical engine in CI is too heavy (it imports ``trade`` and
needs the full price corpus). Instead this script upserts a single synthetic
investment report — a Master Portfolio backtest whose ``metrics_json`` drives
the headline metrics card and whose markdown carries a B016-style wide metrics
table — so the e2e exercises the real DB-backed render path.

Test-only: never wired into deploy.sh or any systemd unit. Idempotent
(upsert by ``strategy_id`` + ``as_of_date``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.investment_report import InvestmentReportRepository

# Slug = f"{strategy_id}-{as_of_date.isoformat()}" (see repository._slug). The
# b040 e2e + global-setup warm-up reference this exact slug.
STRATEGY_ID = "master_portfolio"
AS_OF_DATE = date(2026, 6, 1)
SLUG = f"{STRATEGY_ID}-{AS_OF_DATE.isoformat()}"

_METRICS = {
    "cagr": 0.082,
    "sharpe": 0.91,
    "sortino": 1.18,
    "max_drawdown": -0.146,
    "turnover": 0.37,
}

# B016-style wide metrics table so _extract_tables + the report body render in
# full below the headline card.
_MARKDOWN = """# Master Portfolio — canonical quarterly backtest

> research-only / 仅供研究使用 — historical backtest, not a return forecast.

| method | annualized_return | annualized_volatility | sharpe | max_drawdown | turnover |
| --- | --- | --- | --- | --- | --- |
| master_portfolio | 8.2% | 9.0% | 0.91 | -14.6% | 0.37 |

The Master Portfolio blends the configured sleeves with risk-parity weights,
rebalanced quarterly. Figures above are computed by the real engine over the
unified daily price corpus.
"""


def seed(session: Session) -> None:
    InvestmentReportRepository(session).upsert_report(
        strategy_id=STRATEGY_ID,
        as_of_date=AS_OF_DATE,
        title="Master Portfolio — Canonical Quarterly Backtest",
        markdown=_MARKDOWN,
        metrics=_METRICS,
        computed_at=datetime(2026, 6, 1, 4, 0, tzinfo=UTC),
    )


def main() -> None:
    factory_engine = get_engine()
    with Session(bind=factory_engine, future=True) as session:
        seed(session)
        session.commit()
    print(f"seeded investment report slug={SLUG}")


if __name__ == "__main__":
    main()

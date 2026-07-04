"""B080 F004 fix ② — per-strategy paper base currency (cn_attack CNY / master USD)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.paper.service import (
    activate_paper_account,
    resolve_base_currency,
)

_ON = date(2026, 6, 30)
_NOW = datetime(2026, 6, 30, 12, tzinfo=UTC)


def test_resolve_base_currency_map() -> None:
    assert resolve_base_currency("cn_attack_pure_momentum") == "CNY"
    assert resolve_base_currency("cn_attack_quality_momentum") == "CNY"
    # Master zero-regression: anything not cn_attack stays USD.
    assert resolve_base_currency("master_portfolio") == "USD"
    assert resolve_base_currency("regime_adaptive") == "USD"
    assert resolve_base_currency("anything_else") == "USD"


def test_activate_cn_attack_is_cny(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        # No seeded target → all-cash account; only the currency resolution matters.
        account, plan = activate_paper_account(
            session, strategy_id="cn_attack_pure_momentum", on_date=_ON, now=_NOW
        )
        session.commit()
        assert account.base_currency == "CNY"


def test_activate_master_stays_usd(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        account, _ = activate_paper_account(
            session, strategy_id="master_portfolio", on_date=_ON, now=_NOW
        )
        session.commit()
        assert account.base_currency == "USD"  # zero-regression


def test_explicit_currency_override_wins(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        account, _ = activate_paper_account(
            session,
            strategy_id="cn_attack_pure_momentum",
            on_date=_ON,
            now=_NOW,
            base_currency="USD",
        )
        session.commit()
        assert account.base_currency == "USD"

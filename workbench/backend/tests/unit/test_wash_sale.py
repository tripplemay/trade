"""B048 F004 — wash-sale detection from the fills journal.

Pins: a loss sale (avg_cost > fill_price) paired with a same-symbol
repurchase within 30 days flags; a profitable sale, a repurchase beyond
30 days, or no repurchase does not; multiple symbols resolve independently;
and an undeterminable cost basis is skipped (never fabricated).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.models.fill_journal_entry import FillJournalEntry
from workbench_api.services.wash_sale import detect_wash_sales

_TODAY = date(2026, 6, 30)


def _seed_snapshot(positions: list[dict[str, Any]], *, at: datetime) -> None:
    with Session(get_engine()) as session:
        session.add(
            AccountSnapshot(
                id=f"snap-{at.isoformat()}",
                snapshot_at=at,
                cash=Decimal("0"),
                base_currency="USD",
                positions=positions,
                source="bootstrap",
                created_at=at,
            )
        )
        session.commit()


def _seed_fill(
    *, fid: str, symbol: str, side: str, price: float, at: datetime
) -> None:
    with Session(get_engine()) as session:
        session.add(
            FillJournalEntry(
                id=fid,
                ticket_id=f"tkt-{fid}",
                order_seq=1,
                symbol=symbol,
                side=side,
                shares=Decimal("10"),
                fill_price=Decimal(str(price)),
                commission=Decimal("0"),
                fees=Decimal("0"),
                currency="USD",
                filled_at=at,
                source="manual_entry",
                created_at=at,
            )
        )
        session.commit()


def test_loss_sale_with_repurchase_within_30d_flags(initialised_db: str) -> None:
    # Cost basis 200 (snapshot pre-sale); sell at 150 (loss); rebuy 10 days later.
    _seed_snapshot([{"symbol": "AAPL", "shares": 10, "avg_cost": 200.0}], at=datetime(2026, 5, 1))
    _seed_fill(fid="sell1", symbol="AAPL", side="sell", price=150.0, at=datetime(2026, 5, 10))
    _seed_fill(fid="buy1", symbol="AAPL", side="buy", price=155.0, at=datetime(2026, 5, 20))

    with Session(get_engine()) as session:
        flags = detect_wash_sales(session, today=_TODAY)
        assert len(flags) == 1
        assert flags[0].symbol == "AAPL"
        assert flags[0].last_buy_date == "2026-05-20"
        assert flags[0].days_since == (_TODAY - date(2026, 5, 20)).days


def test_profitable_sale_does_not_flag(initialised_db: str) -> None:
    # Sell ABOVE cost basis → no loss → no wash sale even with a repurchase.
    _seed_snapshot([{"symbol": "AAPL", "shares": 10, "avg_cost": 100.0}], at=datetime(2026, 5, 1))
    _seed_fill(fid="sell1", symbol="AAPL", side="sell", price=150.0, at=datetime(2026, 5, 10))
    _seed_fill(fid="buy1", symbol="AAPL", side="buy", price=155.0, at=datetime(2026, 5, 20))

    with Session(get_engine()) as session:
        assert detect_wash_sales(session, today=_TODAY) == []


def test_repurchase_beyond_30d_does_not_flag(initialised_db: str) -> None:
    _seed_snapshot([{"symbol": "AAPL", "shares": 10, "avg_cost": 200.0}], at=datetime(2026, 5, 1))
    _seed_fill(fid="sell1", symbol="AAPL", side="sell", price=150.0, at=datetime(2026, 5, 10))
    # 31 days after the sale → outside the wash-sale window.
    _seed_fill(fid="buy1", symbol="AAPL", side="buy", price=155.0, at=datetime(2026, 6, 10))

    with Session(get_engine()) as session:
        assert detect_wash_sales(session, today=_TODAY) == []


def test_loss_sale_without_repurchase_does_not_flag(initialised_db: str) -> None:
    _seed_snapshot([{"symbol": "AAPL", "shares": 10, "avg_cost": 200.0}], at=datetime(2026, 5, 1))
    _seed_fill(fid="sell1", symbol="AAPL", side="sell", price=150.0, at=datetime(2026, 5, 10))

    with Session(get_engine()) as session:
        assert detect_wash_sales(session, today=_TODAY) == []


def test_undeterminable_cost_basis_is_skipped(initialised_db: str) -> None:
    # No snapshot carries AAPL → cannot establish a loss → no flag (no fabrication).
    _seed_fill(fid="sell1", symbol="AAPL", side="sell", price=150.0, at=datetime(2026, 5, 10))
    _seed_fill(fid="buy1", symbol="AAPL", side="buy", price=155.0, at=datetime(2026, 5, 20))

    with Session(get_engine()) as session:
        assert detect_wash_sales(session, today=_TODAY) == []


def test_multiple_symbols_resolve_independently(initialised_db: str) -> None:
    _seed_snapshot(
        [
            {"symbol": "AAPL", "shares": 10, "avg_cost": 200.0},  # will loss-sell + rebuy
            {"symbol": "MSFT", "shares": 10, "avg_cost": 100.0},  # profitable sell
            {"symbol": "GLD", "shares": 10, "avg_cost": 200.0},   # loss-sell, no rebuy
        ],
        at=datetime(2026, 5, 1),
    )
    _seed_fill(fid="s-aapl", symbol="AAPL", side="sell", price=150.0, at=datetime(2026, 5, 5))
    _seed_fill(fid="b-aapl", symbol="AAPL", side="buy", price=151.0, at=datetime(2026, 5, 15))
    _seed_fill(fid="s-msft", symbol="MSFT", side="sell", price=180.0, at=datetime(2026, 5, 6))
    _seed_fill(fid="b-msft", symbol="MSFT", side="buy", price=181.0, at=datetime(2026, 5, 16))
    _seed_fill(fid="s-gld", symbol="GLD", side="sell", price=150.0, at=datetime(2026, 5, 7))

    with Session(get_engine()) as session:
        flags = detect_wash_sales(session, today=_TODAY)
        # Only AAPL qualifies (loss + repurchase). Deterministic single flag.
        assert [f.symbol for f in flags] == ["AAPL"]

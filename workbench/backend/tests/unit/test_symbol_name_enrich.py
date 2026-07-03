"""B079 F002 — response-model display-name enrichment (end-to-end).

Proves the DB → resolver → response chain that F002 wires into every symbol-
bearing response model: a held position surfaces its display name (name-primary),
with the curated static seed as the fallback and a live-captured A-share Chinese
name winning over the static English fallback. Exercises the real
``get_latest_account`` service against in-memory SQLite (``initialised_db``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.account_snapshot import (
    DEFAULT_STRATEGY_ID,
    AccountSnapshot,
)
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.symbol_name import SymbolNameRepository
from workbench_api.services.execution import get_latest_account


def _seed_snapshot(session: Session) -> None:
    at = datetime(2026, 7, 3, 12, 0, tzinfo=UTC).replace(tzinfo=None)
    AccountSnapshotRepository(session).upsert(
        AccountSnapshot(
            id="snap-b079-enrich",
            snapshot_at=at,
            strategy_id=DEFAULT_STRATEGY_ID,
            cash=Decimal("1000"),
            base_currency="USD",
            positions=[
                {"symbol": "AAPL", "shares": 10.0, "avg_cost": 150.0},
                {"symbol": "600519.SH", "shares": 5.0, "avg_cost": 1600.0},
                {"symbol": "ZQFAKE", "shares": 1.0, "avg_cost": 1.0},
            ],
            source="ui_edit",
            created_at=at,
        )
    )
    session.commit()


def test_positions_enriched_with_display_names(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        _seed_snapshot(session)
        # A live-captured A-share Chinese name overrides the curated English one.
        SymbolNameRepository(session).upsert_names(
            {"600519.SH": "贵州茅台"}, source="akshare_spot"
        )
        session.commit()

        payload = get_latest_account(session)
        assert payload is not None
        by_symbol = {p.symbol: p for p in payload.positions}

        # US equity: curated static fallback (no live DB row).
        assert by_symbol["AAPL"].name == "Apple Inc."
        # A-share: live akshare Chinese name wins over static English fallback.
        assert by_symbol["600519.SH"].name == "贵州茅台"
        # Unknown/synthetic symbol: no name anywhere → None (raw-code fallback).
        assert by_symbol["ZQFAKE"].name is None

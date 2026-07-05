"""B087 F001 — migration 0041 seeds curated names on the deploy chain (B080 F005 fix).

The auto-deploy chain runs ``alembic upgrade`` (never bootstrap), so migration 0041 must
land the curated display-names itself — and must do so **insert-if-absent** so it never
clobbers an ``akshare_spot`` override (curated = fallback, akshare_spot = priority).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.symbols.names import CURATED_SYMBOL_NAMES

_PREV = "0040_b085_residual_momentum_screen_trial"


def _upgrade(tmp_db_url: str, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)
    command.upgrade(cfg, revision)


def test_alembic_head_seeds_all_curated_names(tmp_db_url: str) -> None:
    _upgrade(tmp_db_url, "head")
    with Session(get_engine()) as session:
        rows = session.execute(
            text("SELECT symbol, name, source FROM symbol_name WHERE source = 'curated'")
        ).all()
        seeded = {r[0]: r[1] for r in rows}
        # every curated name landed on the deploy chain (was production=0 before — B080 F005)
        assert seeded == CURATED_SYMBOL_NAMES
        assert seeded["AAPL"] == "Apple Inc."  # a US name akshare_spot never covers
        assert all(r[2] == "curated" for r in rows)


def test_migration_insert_if_absent_preserves_akshare_override(tmp_db_url: str) -> None:
    # Deploy N: table already has an akshare_spot name for a symbol that is ALSO curated.
    _upgrade(tmp_db_url, _PREV)
    with Session(get_engine()) as session:
        session.execute(
            text(
                "INSERT INTO symbol_name (symbol, name, source, updated_at) "
                "VALUES ('AAPL', :n, 'akshare_spot', :ts)"
            ),
            {"n": "AKSHARE LIVE NAME", "ts": datetime(2026, 7, 4, tzinfo=UTC)},
        )
        session.commit()
    # Deploy N+1 runs 0041 — must NOT overwrite the akshare_spot row.
    _upgrade(tmp_db_url, "head")
    with Session(get_engine()) as session:
        aapl = session.execute(
            text("SELECT name, source FROM symbol_name WHERE symbol = 'AAPL'")
        ).one()
        assert aapl == ("AKSHARE LIVE NAME", "akshare_spot")  # override preserved
        # the other curated names still seeded (fallback where uncovered)
        msft = session.execute(
            text("SELECT name FROM symbol_name WHERE symbol = 'MSFT'")
        ).scalar_one()
        assert msft == "Microsoft Corporation"
        total = session.execute(text("SELECT COUNT(*) FROM symbol_name")).scalar_one()
        assert total == len(CURATED_SYMBOL_NAMES)  # 1 override + (N-1) curated, no dupes

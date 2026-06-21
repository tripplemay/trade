"""B072 F001 — permanent acceptance invariants for the golden → DB full-stack seed.

The DB-seed half of "验收即代码" for B072: the golden full-stack seed
(``scripts/seed_golden_e2e.py``) must push the committed golden fixture into the
DB *deterministically* and produce data the request path renders as a real,
marked Master Portfolio target + a non-empty position-diff — the foundation the
e2e trading loop (F002) drives.

Each invariant has teeth (F004 mutation-checks them): break the seed (drop a
table, mis-mark a price, score the wrong fixture) → the matching test goes red.

The seed lives in ``scripts/`` (test-only, never shipped — same convention as
``seed_e2e_reports.py``), so it is loaded by file/module name rather than as a
package import.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models import Base
from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.db.models.recommendation_snapshot import RecommendationSnapshot
from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.services.execution import get_position_diff
from workbench_api.services.recommendations import get_current_recommendations

# tests/acceptance/<this> → parents[2] is workbench/backend; scripts/ holds the
# test-only seed. Put it on sys.path so its top-level ``import seed_e2e_reports``
# resolves, then load the seed module by name.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
seed: ModuleType = importlib.import_module("seed_golden_e2e")


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _content_fingerprint(sess: Session) -> dict[str, list[str]]:
    """A row-content fingerprint of the seeded tables (UUIDs excluded) as stable
    strings, so a re-seed of the same golden fixture must produce an identical
    fingerprint."""

    recs = sorted(
        f"{r.symbol}|{round(float(r.target_weight), 6)}|{r.sleeve}"
        for r in sess.execute(select(RecommendationSnapshot)).scalars()
    )
    prices = sorted(
        f"{p.symbol}|{p.obs_date.isoformat()}|{round(float(p.close), 6)}"
        for p in sess.execute(select(PriceSnapshot)).scalars()
    )
    acc = AccountSnapshotRepository(sess).latest()
    account = (
        [
            f"{acc.id}|{acc.cash}|"
            + repr(sorted((p["symbol"], p["shares"]) for p in acc.positions))
        ]
        if acc is not None
        else []
    )
    return {"recommendations": recs, "prices": prices, "account": account}


def test_golden_seed_persists_marked_golden_target(session: Session) -> None:
    """The seed scores the real Master target on golden, sums to 1.0, and every
    target symbol is marked from the seeded golden closes (no missing prices)."""

    seed.seed_all(session)
    session.commit()

    response = get_current_recommendations(session)
    assert response.account_present is True
    assert len(response.target_positions) >= 3, "golden target collapsed (degenerate?)"
    assert sum(p.target_weight for p in response.target_positions) == pytest.approx(
        1.0, abs=1e-3
    )
    # Every target is priced from the seeded golden marks → the diff is rebalanceable.
    assert all(p.has_mark for p in response.target_positions)

    spy_marks = PriceSnapshotRepository(session).latest_two_by_symbol("SPY")
    assert len(spy_marks) == 2, "DbPriceProvider needs two closes to mark SPY"


def test_golden_seed_position_diff_is_marked_with_buys(session: Session) -> None:
    """On the seeded closed-loop account the position-diff values holdings at the
    golden marks (equity > cash) and surfaces real buys with reference prices —
    nothing falls into ``unmatched`` (every symbol is golden-priced)."""

    seed.seed_all(session)
    session.commit()

    diff = get_position_diff(session)
    assert diff.total_equity > float(seed.ACCOUNT_CASH), "held marks did not lift NAV"
    buys = [row for row in diff.diff if row.delta_shares > 1e-9]
    assert buys, "golden target produced no buys against the seeded account"
    assert all(row.reference_price is not None for row in buys)
    assert diff.unmatched == [], "a target symbol was missing a golden mark"


def test_golden_seed_is_deterministic(initialised_db: str) -> None:  # noqa: ARG001
    """Same golden fixture → same DB content. Seed a fresh schema twice (UUIDs
    aside) and assert the row-content fingerprint is identical."""

    engine = get_engine()
    factory = sessionmaker(bind=engine, autoflush=False, future=True)

    first = factory()
    seed.seed_all(first)
    first.commit()
    fingerprint_a = _content_fingerprint(first)
    first.close()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    second = factory()
    seed.seed_all(second)
    second.commit()
    fingerprint_b = _content_fingerprint(second)
    second.close()

    assert fingerprint_a == fingerprint_b
    assert fingerprint_a["recommendations"], "determinism check ran on an empty seed"

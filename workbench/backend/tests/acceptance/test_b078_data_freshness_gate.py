"""B078 F002 — permanent acceptance guard: the data-freshness gate has teeth.

The B078 freeze was silent: ``recommendation_snapshot`` ``as_of`` and the A-share
``price_snapshot`` both froze on 2026-06-22 and nothing went red for four days.
This turns "a frozen snapshot must be caught" into a CI regression: seed a FRESH
snapshot → the gate passes; seed a STALE one (the freeze) → the gate flags it. If
a future change blunts the freshness check, the teeth tests go red.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.data_refresh.freshness import (
    assess_as_of_freshness,
    latest_cn_price_as_of,
    latest_recommendation_as_of,
)
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.strategy_modes.registry import (
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
)

NOW = date(2026, 6, 26)
_FETCHED_AT = datetime(2026, 6, 26, 2, 0, tzinfo=UTC)
_ROWS: list[dict[str, object]] = [
    {"symbol": "600519.SH", "sleeve": "cn_attack", "target_weight": 0.5},
    {"symbol": "000858.SZ", "sleeve": "cn_attack", "target_weight": 0.5},
]


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _seed_reco(session: Session, as_of: date) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        as_of_date=as_of,
        rows=_ROWS,
        master_meta={"data_source": "real"},
    )
    session.commit()


def _seed_cn_price(session: Session, obs_date: date) -> None:
    repo = PriceSnapshotRepository(session)
    for symbol in ("600519.SH", "000858.SZ"):
        repo.save_if_new(
            symbol=symbol,
            obs_date=obs_date,
            close=100.0,
            source="test",
            fetched_at=_FETCHED_AT,
        )
    session.commit()


def test_fresh_recommendation_snapshot_passes_gate(session: Session) -> None:
    _seed_reco(session, as_of=date(2026, 6, 25))  # 1 business day before NOW
    as_of = latest_recommendation_as_of(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID)
    assert as_of == date(2026, 6, 25)
    assert assess_as_of_freshness("reco", as_of, NOW).is_fresh is True


def test_stale_recommendation_snapshot_is_caught(session: Session) -> None:
    # The B078 freeze: as_of stuck weeks back while NOW marches on.
    _seed_reco(session, as_of=date(2026, 5, 20))
    as_of = latest_recommendation_as_of(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID)
    verdict = assess_as_of_freshness("reco", as_of, NOW)
    assert verdict.is_fresh is False
    assert verdict.age_business_days is not None and verdict.age_business_days > 3


def test_fresh_cn_price_snapshot_passes_gate(session: Session) -> None:
    _seed_cn_price(session, obs_date=date(2026, 6, 25))
    as_of = latest_cn_price_as_of(session)
    assert as_of == date(2026, 6, 25)
    assert assess_as_of_freshness("cn_price", as_of, NOW).is_fresh is True


def test_stale_cn_price_snapshot_is_caught(session: Session) -> None:
    # The exact B078 symptom: A-share prices frozen Mon 2026-06-22, the freeze
    # discovered Fri 2026-06-26 (= 4 business days) — caught with the SHIPPED
    # DEFAULT threshold (no override), so this faithfully reproduces the magnitude
    # of the real freeze rather than an exaggerated margin.
    _seed_cn_price(session, obs_date=date(2026, 6, 22))
    as_of = latest_cn_price_as_of(session)
    assert as_of == date(2026, 6, 22)
    verdict = assess_as_of_freshness("cn_price", as_of, NOW)  # NOW = 2026-06-26
    assert verdict.is_fresh is False
    assert verdict.age_business_days == 4


def test_no_snapshot_at_all_is_not_fresh(session: Session) -> None:
    assert latest_recommendation_as_of(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID) is None
    assert latest_cn_price_as_of(session) is None
    assert assess_as_of_freshness("reco", None, NOW).is_fresh is False

"""B035 F001 — MarketContextObservation model + repository + alembic 0007.

Mirrors :mod:`tests.unit.test_news_embedding_repo` (one shared session,
closed before teardown so the SQLite file is never locked).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.market_context import MarketContextObservation
from workbench_api.db.repositories.market_context import MarketContextRepository


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    yield SimpleNamespace(
        session=session, factory=factory, repo=MarketContextRepository(session)
    )
    session.close()


def _save(
    repo: MarketContextRepository, **kw: object
) -> MarketContextObservation | None:
    defaults = dict(
        series_id="DGS10",
        source="fred",
        obs_date=date(2026, 6, 1),
        value=4.25,
        snapshot_path="fred/2026-06-01/DGS10.json",
        fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    defaults.update(kw)
    return repo.save_if_new(**defaults)  # type: ignore[arg-type]


def test_save_if_new_inserts_first_row(ctx: SimpleNamespace) -> None:
    row = _save(ctx.repo)
    assert row is not None
    assert row.series_id == "DGS10"
    assert row.source == "fred"
    assert row.obs_date == date(2026, 6, 1)
    assert row.value == 4.25
    assert ctx.repo.count() == 1


def test_save_if_new_is_idempotent_by_series_and_date(ctx: SimpleNamespace) -> None:
    first = _save(ctx.repo, value=4.25)
    second = _save(ctx.repo, value=4.99)  # same (series_id, obs_date)
    assert first is not None
    assert second is None
    assert ctx.repo.count() == 1


def test_save_if_new_allows_same_series_different_date(ctx: SimpleNamespace) -> None:
    _save(ctx.repo, obs_date=date(2026, 6, 1))
    other = _save(ctx.repo, obs_date=date(2026, 6, 2))
    assert other is not None
    assert ctx.repo.count() == 2


def test_value_round_trips_as_float(ctx: SimpleNamespace) -> None:
    _save(ctx.repo, series_id="CPIAUCSL", value=312.345)
    ctx.session.expire_all()
    row = ctx.repo.get_by_series_and_date("CPIAUCSL", date(2026, 6, 1))
    assert row is not None
    assert isinstance(row.value, float)
    assert row.value == pytest.approx(312.345)


def test_latest_by_series_returns_newest(ctx: SimpleNamespace) -> None:
    for day, val in ((1, 4.1), (3, 4.3), (2, 4.2)):
        _save(ctx.repo, obs_date=date(2026, 6, day), value=val)
    latest = ctx.repo.latest_by_series("DGS10")
    assert latest is not None
    assert latest.obs_date == date(2026, 6, 3)
    assert latest.value == pytest.approx(4.3)
    assert ctx.repo.latest_by_series("MISSING") is None


def test_list_by_series_since_and_limit(ctx: SimpleNamespace) -> None:
    for day in range(1, 6):
        _save(ctx.repo, obs_date=date(2026, 6, day), value=float(day))
    rows = ctx.repo.list_by_series("DGS10", since=date(2026, 6, 3), limit=2)
    assert [r.obs_date for r in rows] == [date(2026, 6, 5), date(2026, 6, 4)]


def test_columns_match_schema(ctx: SimpleNamespace) -> None:  # noqa: ARG001
    columns = {
        c["name"]
        for c in inspect(get_engine()).get_columns("market_context_observation")
    }
    assert columns == {
        "id",
        "series_id",
        "source",
        "obs_date",
        "value",
        "snapshot_path",
        "fetched_at",
    }


def test_unique_constraint_blocks_duplicate_via_orm(ctx: SimpleNamespace) -> None:
    from sqlalchemy.exc import IntegrityError

    _save(ctx.repo)
    dup = MarketContextObservation(
        id=uuid4(),
        series_id="DGS10",
        source="fred",
        obs_date=date(2026, 6, 1),  # same (series_id, obs_date)
        value=9.9,
        snapshot_path="x",
        fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    ctx.session.add(dup)
    with pytest.raises(IntegrityError):
        ctx.session.flush()
    ctx.session.rollback()


def test_alembic_upgrade_creates_table(tmp_db_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option(
        "script_location", f"{backend_root}/workbench_api/db/migrations"
    )
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)

    command.upgrade(cfg, "0007_b035_market_context")
    inspector = inspect(get_engine())
    assert "market_context_observation" in set(inspector.get_table_names())
    indexes = {
        idx["name"] for idx in inspector.get_indexes("market_context_observation")
    }
    assert {"ix_market_context_series", "ix_market_context_obs_date"}.issubset(indexes)
    uniques = {
        uc["name"]
        for uc in inspector.get_unique_constraints("market_context_observation")
    }
    assert "uq_market_context_series_date" in uniques

    command.downgrade(cfg, "0006_b034_news_embedding")
    inspector = inspect(get_engine())
    after = set(inspector.get_table_names())
    assert "market_context_observation" not in after
    assert "news_embedding" in after  # B034 table survives the downgrade.

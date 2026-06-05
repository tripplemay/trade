"""B036 F001 — AdvisorRecommendation model + repository + alembic 0008."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.advisor_recommendation import (
    STATUS_OK,
    AdvisorRecommendation,
)
from workbench_api.db.repositories.advisor_recommendation import (
    AdvisorRecommendationRepository,
)


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    yield SimpleNamespace(session=session, repo=AdvisorRecommendationRepository(session))
    session.close()


def _row(
    sleeve: str = "satellite_us_quality", *, when: datetime | None = None
) -> AdvisorRecommendation:
    return AdvisorRecommendation(
        id=uuid4(),
        sleeve=sleeve,
        advice_json={"advice": "a", "rationale": "r"},
        quant_signal_sha="sha256:abc",
        references_json=[{"quant_signal_sha": "sha256:abc", "news_urls": ["https://a"]}],
        model="claude-haiku-4.5",
        status=STATUS_OK,
        generated_at=when or datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
    )


def test_save_and_round_trip(ctx: SimpleNamespace) -> None:
    saved = ctx.repo.save(_row())
    assert saved.id is not None
    fetched = ctx.repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.advice_json == {"advice": "a", "rationale": "r"}
    assert fetched.references_json[0]["news_urls"] == ["https://a"]


def test_latest_by_sleeve_returns_newest(ctx: SimpleNamespace) -> None:
    base = datetime(2026, 6, 5, tzinfo=UTC)
    for offset in (0, 2, 1):
        ctx.repo.save(_row(when=base + timedelta(hours=offset)))
    latest = ctx.repo.latest_by_sleeve("satellite_us_quality")
    assert latest is not None
    # SQLite drops tzinfo on read-back; compare tz-agnostically. The point is
    # ordering picks the newest (hour=2), not an exact tz round-trip.
    assert latest.generated_at.replace(tzinfo=None) == (
        base + timedelta(hours=2)
    ).replace(tzinfo=None)
    assert ctx.repo.latest_by_sleeve("missing") is None


def test_columns_match_schema(ctx: SimpleNamespace) -> None:  # noqa: ARG001
    columns = {
        c["name"] for c in inspect(get_engine()).get_columns("advisor_recommendation")
    }
    assert columns == {
        "id",
        "sleeve",
        "advice_json",
        "quant_signal_sha",
        "references_json",
        "model",
        "status",
        "generated_at",
    }


def test_alembic_upgrade_creates_table(tmp_db_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)

    command.upgrade(cfg, "0008_b036_advisor")
    inspector = inspect(get_engine())
    assert "advisor_recommendation" in set(inspector.get_table_names())
    indexes = {idx["name"] for idx in inspector.get_indexes("advisor_recommendation")}
    assert {
        "ix_advisor_recommendation_sleeve",
        "ix_advisor_recommendation_generated_at",
    }.issubset(indexes)

    command.downgrade(cfg, "0007_b035_market_context")
    inspector = inspect(get_engine())
    after = set(inspector.get_table_names())
    assert "advisor_recommendation" not in after
    assert "market_context_observation" in after  # B035 table survives

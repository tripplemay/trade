"""B036 F001 — grounding assembly (real services) + synthetic builder."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.advisor.grounding import (
    SHA_PREFIX,
    build_grounding,
    grounding_from_synthetic,
)
from workbench_api.db.engine import get_engine


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    yield SimpleNamespace(session=session)
    session.close()


def test_build_grounding_known_sleeve_has_quant_and_sha(ctx: SimpleNamespace) -> None:
    g = build_grounding(ctx.session, "satellite_us_quality")
    assert g.quant_present is True
    assert g.quant_signal_sha.startswith(SHA_PREFIX)
    assert g.quant_signal_payload  # non-empty canonical payload
    # No news / market ingested in the test DB → empty but valid.
    assert g.news == []
    # market context catalog always returns the 6 series (values may be None).
    assert len(g.market_context) == 6


def test_build_grounding_sha_is_deterministic(ctx: SimpleNamespace) -> None:
    a = build_grounding(ctx.session, "satellite_us_quality").quant_signal_sha
    b = build_grounding(ctx.session, "satellite_us_quality").quant_signal_sha
    assert a == b


def test_build_grounding_unknown_sleeve_has_no_quant(ctx: SimpleNamespace) -> None:
    g = build_grounding(ctx.session, "no_such_sleeve")
    assert g.quant_present is False
    assert g.quant_signal_sha == ""


def test_build_grounding_market_context_has_catalog_series(ctx: SimpleNamespace) -> None:
    g = build_grounding(ctx.session, "satellite_us_quality")
    assert {m.series_id for m in g.market_context} == {
        "DGS10",
        "VIXCLS",
        "CPIAUCSL",
        "SPY",
        "QQQ",
        "UUP",
    }


def test_grounding_from_synthetic_empty_news_set() -> None:
    g = grounding_from_synthetic(
        "master", {"quant_signal_sha": "sha256:x", "quant_signal_payload": "p"}
    )
    assert g.news == []
    assert g.news_urls == set()


def test_grounding_from_synthetic_maps_fields() -> None:
    g = grounding_from_synthetic(
        "master",
        {
            "quant_signal_sha": "sha256:test-quant-001",
            "quant_signal_payload": "Master target weights ...",
            "news_set": [
                {"url": "https://example.com/x", "title": "T", "published_at": "2026-05-20"}
            ],
        },
    )
    assert g.quant_present is True
    assert g.quant_signal_sha == "sha256:test-quant-001"
    assert g.news_urls == {"https://example.com/x"}

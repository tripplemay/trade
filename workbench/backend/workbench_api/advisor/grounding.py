"""B036 F001 — advisor grounding assembly.

``build_grounding(session, sleeve)`` gathers the three grounded inputs
the AI advisor is allowed to reason over (B036 spec §4.3):

* **quant signal** — derived read-only from the strategy registry
  (``services.strategies``) for the sleeve, serialised canonically and
  hashed (``sha256:<hex>``). This is the ``quant_signal_sha`` every
  actionable advice line must cite (boundary (d)). The advisor never
  modifies signal generation — it only reads + hashes it.
* **news** — B034 ``NewsAssociationService.news_for_sleeve`` (each item
  carries a ``url`` that advice may cite).
* **market context** — B035 latest value per series (context only).

A :class:`Grounding` is also constructible directly from a raw dict (the
B032 red-team samples' ``synthetic_input``) via :func:`grounding_from_synthetic`
so the safety gate exercises the real advisor against adversarial inputs.

When the sleeve has no quant signal (unknown sleeve / empty registry),
``quant_present`` is ``False`` and the service short-circuits to
``INSUFFICIENT_GROUNDING`` rather than asking the model to invent one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.news.association import NewsAssociationService
from workbench_api.services.market_context import get_market_context
from workbench_api.services.strategies import get_strategy, list_strategies

SHA_PREFIX = "sha256:"


@dataclass(frozen=True, slots=True)
class GroundingNewsItem:
    url: str
    title: str
    published_at: str


@dataclass(frozen=True, slots=True)
class GroundingMarketItem:
    series_id: str
    label: str
    value: float | None
    date: str | None


@dataclass(frozen=True, slots=True)
class Grounding:
    """The complete, citation-checkable input set for one advice call."""

    sleeve: str
    quant_present: bool
    quant_signal_sha: str
    quant_signal_payload: str
    news: list[GroundingNewsItem] = field(default_factory=list)
    market_context: list[GroundingMarketItem] = field(default_factory=list)

    @property
    def news_urls(self) -> set[str]:
        """The set of URLs advice references may cite (boundary (d))."""

        return {item.url for item in self.news}


def _quant_signal_for_sleeve(sleeve: str) -> tuple[bool, str, str]:
    """Return ``(present, payload, sha)`` for the sleeve's quant signal.

    Read-only over the strategy registry: gathers the strategies whose
    ``sleeve`` matches + their config bags, serialises them canonically
    (sorted keys, stable separators) and hashes. An empty match → no
    quant signal."""

    entries = [
        s for s in list_strategies().strategies if s.sleeve == sleeve
    ]
    if not entries:
        return False, "", ""
    catalog: list[dict[str, Any]] = []
    for summary in entries:
        detail = get_strategy(summary.id)
        catalog.append(
            {
                "id": summary.id,
                "name": summary.name,
                "config": detail.config if detail is not None else {},
            }
        )
    payload = json.dumps(
        {"sleeve": sleeve, "strategies": catalog},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    sha = SHA_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return True, payload, sha


def build_grounding(
    session: Session, sleeve: str, *, news_limit: int = 10
) -> Grounding:
    """Assemble the grounding for ``sleeve`` from quant + news + market."""

    present, payload, sha = _quant_signal_for_sleeve(sleeve)

    relevances = NewsAssociationService(session).news_for_sleeve(
        sleeve, limit=news_limit
    )
    news = [
        GroundingNewsItem(
            url=r.url, title=r.title, published_at=r.published_at.isoformat()
        )
        for r in relevances
    ]

    market = [
        GroundingMarketItem(
            series_id=s.series_id,
            label=s.label,
            value=s.latest_value,
            date=s.latest_date,
        )
        for s in get_market_context(session).series
    ]

    return Grounding(
        sleeve=sleeve,
        quant_present=present,
        quant_signal_sha=sha,
        quant_signal_payload=payload,
        news=news,
        market_context=market,
    )


def grounding_from_synthetic(sleeve: str, synthetic_input: Mapping[str, Any]) -> Grounding:
    """Build a :class:`Grounding` from a red-team sample's ``synthetic_input``.

    Lets the B032 safety gate run the **real** advisor against adversarial
    inputs without touching the live DB / services. The synthetic shape is
    ``{quant_signal_sha, quant_signal_payload, news_set:[{url,title,...}]}``."""

    raw_news: Sequence[Mapping[str, Any]] = synthetic_input.get("news_set", []) or []
    news = [
        GroundingNewsItem(
            url=str(item.get("url", "")),
            title=str(item.get("title", "")),
            published_at=str(item.get("published_at", "")),
        )
        for item in raw_news
    ]
    sha = str(synthetic_input.get("quant_signal_sha", ""))
    return Grounding(
        sleeve=sleeve,
        quant_present=bool(sha),
        quant_signal_sha=sha,
        quant_signal_payload=str(synthetic_input.get("quant_signal_payload", "")),
        news=news,
        market_context=[],
    )

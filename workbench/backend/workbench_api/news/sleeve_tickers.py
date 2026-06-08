"""B034 F002 — sleeve → constituent tickers resolution.

The news↔sleeve association needs each sleeve's constituent tickers to
compute the hard match (``sleeve tickers ∩ news mentions``). The
workbench's sleeves come from the strategy registry
(:func:`workbench_api.services.strategies.sleeve_strategies`, sleeve
field — excludes the portfolio-level master flagship). Only two
of those carry tickers in the B034 news universe (B025 27 equities +
the 4 master ETFs the news CLI ingests):

* ``satellite_us_quality`` → the B025 US Quality 27 real tickers
  (``scripts.universe_us_quality.US_QUALITY_REAL_TICKERS``);
* ``master`` → the 4 master ETFs in the news universe (SPY/QQQ/EFA/EEM).

Other sleeves (``regime`` / ``risk_parity`` etc.) trade instruments the
news CLI does not ingest, so they resolve to an empty constituent set
and :meth:`NewsAssociationService.news_for_sleeve` returns no rows for
them — correct, not an error.

This module is **read-only** with respect to the strategy registry
(B034 spec §10: don't touch the strategies contract) — it only reads
the sleeve labels to validate the requested sleeve is real.
"""

from __future__ import annotations

from functools import lru_cache

# The 4 master ETFs the news CLI ingests (news/cli.py universe tail).
_MASTER_NEWS_ETFS: tuple[str, ...] = ("SPY", "QQQ", "EFA", "EEM")


@lru_cache(maxsize=1)
def _sleeve_constituents() -> dict[str, tuple[str, ...]]:
    """Build (and memoise) the sleeve → tickers map.

    The US Quality constituents come from
    :func:`workbench_api.news.ticker_match.equity_universe_tickers`, which
    reads ``universe.csv`` via the stdlib ``csv`` loader — **no pandas /
    no ``scripts`` import**. That keeps this off the request path's
    dependency on the heavy ``scripts.universe_us_quality`` (pandas),
    which the leaner production / frontend-CI backend install does not
    carry — importing it in a request handler 500s there (B034 F003
    fix-round root cause)."""

    from workbench_api.news.ticker_match import equity_universe_tickers

    return {
        "satellite_us_quality": equity_universe_tickers(),
        "master": _MASTER_NEWS_ETFS,
    }


@lru_cache(maxsize=1)
def _known_sleeve_labels() -> frozenset[str]:
    """Sleeve labels the strategy registry exposes, plus ``master``.

    Read-only validation source — a requested sleeve outside this set is
    treated as "no constituents" rather than raising, so the API stays
    forgiving of an unknown query."""

    from workbench_api.services.strategies import sleeve_strategies

    labels = {s.sleeve for s in sleeve_strategies()}
    labels.add("master")
    return frozenset(labels)


def tickers_for_sleeve(sleeve: str) -> tuple[str, ...]:
    """Return the sleeve's constituent tickers, or ``()`` when the sleeve
    is unknown or carries no news-universe tickers."""

    return _sleeve_constituents().get(sleeve, ())


def is_known_sleeve(sleeve: str) -> bool:
    """Whether ``sleeve`` is a sleeve the strategy registry knows about."""

    return sleeve in _known_sleeve_labels()


def build_sleeve_query_text(sleeve: str) -> str:
    """Build the text embedded as the sleeve's semantic query vector.

    ``"<sleeve label> <constituent company tickers>"`` — the sleeve name
    plus its tickers gives bge-m3 enough signal to rank topically-related
    news above unrelated ones. Company names are intentionally not
    expanded here (the ticker symbols keep the query compact and
    deterministic); the embedding model handles the rest."""

    tickers = tickers_for_sleeve(sleeve)
    return f"{sleeve.replace('_', ' ')} {' '.join(tickers)}".strip()

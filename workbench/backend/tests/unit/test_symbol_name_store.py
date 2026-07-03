"""B079 F001 — symbol_name store: repository, curated seed, and resolver.

Exercises the isolated ``symbol_name`` table (the lightweight symbol → display
name lookup) against in-memory SQLite (``initialised_db``; no network):

- :class:`SymbolNameRepository` batch ``get_names`` (pure DB, missing omitted,
  empty short-circuit) + ``upsert_names`` (insert, in-place replace, blank skip,
  provenance + timestamp).
- :data:`CURATED_SYMBOL_NAMES` covers the three bounded static universes.
- :func:`resolve_symbol_names` merges curated ∪ DB with the live DB row winning
  (a captured A-share Chinese name overrides the static English fallback) and
  normalises casing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.symbol_name import SymbolNameRepository
from workbench_api.symbols.names import (
    CURATED_SYMBOL_NAMES,
    normalize_symbol,
    resolve_symbol_names,
)

# --------------------------------------------------------------------------- #
# repository
# --------------------------------------------------------------------------- #


def test_get_names_empty_input_short_circuits(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        assert SymbolNameRepository(session).get_names([]) == {}


def test_upsert_then_get_names_returns_stored_subset(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolNameRepository(session)
        written = repo.upsert_names(
            {"600519.SH": "贵州茅台", "AAPL": "Apple Inc."}, source="curated"
        )
        session.commit()
        assert written == 2
        # Missing symbols are simply absent (caller falls back to the raw code).
        got = repo.get_names(["600519.SH", "AAPL", "NOPE.SZ"])
        assert got == {"600519.SH": "贵州茅台", "AAPL": "Apple Inc."}


def test_upsert_replaces_in_place_and_records_provenance(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolNameRepository(session)
        stamp = datetime(2026, 7, 3, 9, 0, tzinfo=UTC)
        repo.upsert_names({"600519.SH": "Kweichow Moutai"}, source="curated", updated_at=stamp)
        session.commit()
        assert repo.count() == 1

        # A fresher live capture overrides the same symbol (no duplicate row).
        newer = datetime(2026, 7, 4, 9, 0, tzinfo=UTC)
        repo.upsert_names({"600519.SH": "贵州茅台"}, source="akshare_spot", updated_at=newer)
        session.commit()
        assert repo.count() == 1
        row = repo.get_by_id("600519.SH")
        assert row is not None
        assert row.name == "贵州茅台"
        assert row.source == "akshare_spot"


def test_upsert_skips_blank_names(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = SymbolNameRepository(session)
        # A missing name must fall back to the raw code, never store an empty string.
        written = repo.upsert_names(
            {"AAPL": "Apple Inc.", "BLANK.SZ": "   ", "EMPTY.SH": ""}, source="curated"
        )
        session.commit()
        assert written == 1
        assert repo.get_names(["AAPL", "BLANK.SZ", "EMPTY.SH"]) == {"AAPL": "Apple Inc."}


# --------------------------------------------------------------------------- #
# curated static seed
# --------------------------------------------------------------------------- #


def test_curated_covers_the_three_static_universes() -> None:
    # US equity (news._UNIVERSE_NAMES), ETF (hand-curated), CN/HK (trade twin).
    assert CURATED_SYMBOL_NAMES["AAPL"] == "Apple Inc."
    assert CURATED_SYMBOL_NAMES["SPY"] == "SPDR S&P 500 ETF Trust"
    assert CURATED_SYMBOL_NAMES["0700.HK"] == "Tencent"
    assert CURATED_SYMBOL_NAMES["600519.SH"] == "Kweichow Moutai"
    # ~68 bounded symbols; keys normalised (uppercased); no blank name.
    assert len(CURATED_SYMBOL_NAMES) >= 60
    assert all(k == normalize_symbol(k) for k in CURATED_SYMBOL_NAMES)
    assert all(v.strip() for v in CURATED_SYMBOL_NAMES.values())


def test_cn_hk_curated_names_match_trade_authority() -> None:
    """The locally-copied CN/HK names must stay in lockstep with the trade-side
    authority ``REAL_HK_CHINA_UNIVERSE`` (copied, not imported, to keep the
    display module free of the heavy trade/pandas deps)."""

    from trade.data.hk_china_real_universe import (  # type: ignore[import-untyped]
        REAL_HK_CHINA_UNIVERSE,
    )

    from workbench_api.symbols.names import _CN_HK_NAMES

    authority = {entry.ticker: entry.name for entry in REAL_HK_CHINA_UNIVERSE}
    assert authority == _CN_HK_NAMES


# --------------------------------------------------------------------------- #
# resolver — curated ∪ DB, DB wins
# --------------------------------------------------------------------------- #


def test_resolver_falls_back_to_curated_when_db_empty(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        # Nothing seeded into the DB yet → the curated static map still resolves,
        # so coverage never depends on a seed job having run.
        names = resolve_symbol_names(session, ["AAPL", "0700.HK"])
        assert names["AAPL"] == "Apple Inc."
        assert names["0700.HK"] == "Tencent"


def test_resolver_lets_live_db_name_win_over_curated(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        SymbolNameRepository(session).upsert_names(
            {"600519.SH": "贵州茅台"}, source="akshare_spot"
        )
        session.commit()
        # Curated English fallback exists (Kweichow Moutai) but the live Chinese
        # capture is fresher/better → DB wins.
        names = resolve_symbol_names(session, ["600519.SH"])
        assert names["600519.SH"] == "贵州茅台"


def test_resolver_normalises_case_and_omits_unknown(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        names = resolve_symbol_names(session, ["aapl", "  0700.hk ", "ZZZ.UNKNOWN"])
        assert names["AAPL"] == "Apple Inc."
        assert names["0700.HK"] == "Tencent"
        assert "ZZZ.UNKNOWN" not in names  # unknown → absent (raw-code fallback)

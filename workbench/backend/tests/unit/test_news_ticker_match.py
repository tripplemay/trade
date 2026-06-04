"""B034 F002 — deterministic ticker mention matcher.

Pins the precision contract from the spec: whole-word matching (so
``APP`` never hits ``AAPL``), company-name aliases, ETF aliases, the
English-word collision rule (``cat`` ≠ Caterpillar), and ``ZQ*``
exclusion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workbench_api.news import ticker_match
from workbench_api.news.ticker_match import (
    _UNIVERSE_NAMES,
    _parse_universe_csv,
    build_ticker_dictionary,
    cik_to_ticker_map,
    equity_universe_tickers,
    match_mentions,
)


def test_matches_bare_symbol() -> None:
    assert match_mentions("AAPL rallied after the print") == ["AAPL"]


def test_matches_company_name_and_short_alias() -> None:
    assert match_mentions("Apple Inc. reported record revenue") == ["AAPL"]
    assert match_mentions("Shares of Apple slipped") == ["AAPL"]


def test_company_alias_is_case_insensitive() -> None:
    assert match_mentions("microsoft beat estimates") == ["MSFT"]


def test_partial_word_does_not_match() -> None:
    """``APP`` is a different token than ``AAPL`` — whole-word matching
    must not produce a false positive."""

    assert match_mentions("The APP store grew") == []
    assert match_mentions("apples to oranges") == []  # plural "apples" is a different token


def test_synthetic_zq_tickers_excluded() -> None:
    assert match_mentions("ZQAI and ZQPT surged") == []


def test_english_word_collision_symbol_matched_by_name_only() -> None:
    """``CAT`` collides with the word "cat" → the bare symbol is not a
    match token; only the company name resolves Caterpillar."""

    assert match_mentions("the cat sat on the mat") == []
    assert match_mentions("Caterpillar Inc. lifted guidance") == ["CAT"]


def test_single_letter_ticker_visa_matched_by_name_only() -> None:
    assert match_mentions("Visa Inc. processed more volume") == ["V"]
    # A bare "V" token must not flag Visa (collision rule).
    assert match_mentions("grade V steel") == []


def test_etf_symbol_and_alias() -> None:
    assert match_mentions("SPY closed lower") == ["SPY"]
    assert match_mentions("Invesco QQQ saw inflows") == ["QQQ"]


def test_multiple_mentions_sorted_and_deduped() -> None:
    text = "Apple and Microsoft both rose; AAPL led the gainers"
    assert match_mentions(text) == ["AAPL", "MSFT"]


def test_dictionary_excludes_synthetic_and_covers_universe() -> None:
    table = build_ticker_dictionary()
    assert "AAPL" in table.tickers
    assert "SPY" in table.tickers
    assert not any(t.startswith("ZQ") for t in table.tickers)
    # 27 real equities + 4 ETFs.
    assert len(table.tickers) == 31


def test_cik_to_ticker_map_resolves_known_and_skips_synthetic() -> None:
    cik_map = cik_to_ticker_map()
    # Apple's CIK is 320193 (B029 fixture).
    assert cik_map.get(320193) == "AAPL"
    assert all(not ticker.startswith("ZQ") for ticker in cik_map.values())


def test_universe_constant_matches_csv() -> None:
    """Drift guard: the in-code ``_UNIVERSE_NAMES`` must mirror the B025
    fixture CSV exactly. The runtime reads the constant (the CSV is not
    in the deploy artifact — F004 L2 fix), so this CI-only check is what
    keeps the two in sync."""

    assert _parse_universe_csv() == _UNIVERSE_NAMES


def test_equity_universe_tickers_resolves_without_fixture_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for the F004 L2 production 500 (2026-06-04): the request
    path must resolve the universe with **no** dependency on the
    un-deployed fixture CSV. Point ``UNIVERSE_CSV`` at a missing path and
    assert resolution still works — before the fix this raised
    ``FileNotFoundError`` (the exact production failure)."""

    monkeypatch.setattr(
        ticker_match, "UNIVERSE_CSV", Path("/nonexistent/universe.csv")
    )
    build_ticker_dictionary.cache_clear()

    tickers = equity_universe_tickers()
    assert len(tickers) == 27
    assert "AAPL" in tickers
    assert not any(t.startswith("ZQ") for t in tickers)

    # The full dictionary build (ingest path) is also file-free now.
    table = build_ticker_dictionary()
    assert "AAPL" in table.tickers
    assert match_mentions("Apple Inc. reported") == ["AAPL"]

    build_ticker_dictionary.cache_clear()

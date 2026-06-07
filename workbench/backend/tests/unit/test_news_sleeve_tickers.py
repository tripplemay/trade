"""B034 F002 / F003 fix-round — sleeve → ticker resolution.

Regression guard for the F003 frontend-CI failure: ``sleeve_tickers``
must resolve the US Quality constituents **without importing
``scripts.universe_us_quality`` (pandas)** — that module is fine for the
CLI but 500s on the API request path in the leaner production /
frontend-CI backend install which carries no pandas. The constituents
come from the stdlib-csv universe loader instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

from workbench_api.news.sleeve_tickers import (
    build_sleeve_query_text,
    is_known_sleeve,
    tickers_for_sleeve,
)

_SLEEVE_TICKERS_SRC = (
    Path(__file__).resolve().parents[1].parent
    / "workbench_api"
    / "news"
    / "sleeve_tickers.py"
)


def test_satellite_sleeve_resolves_27_real_tickers() -> None:
    tickers = tickers_for_sleeve("satellite_us_quality")
    assert len(tickers) == 27
    assert "AAPL" in tickers
    assert "XOM" in tickers
    assert not any(t.startswith("ZQ") for t in tickers)


def test_master_sleeve_resolves_news_universe_etfs() -> None:
    assert tickers_for_sleeve("master") == ("SPY", "QQQ", "EFA", "EEM")


def test_unknown_sleeve_resolves_empty() -> None:
    assert tickers_for_sleeve("regime") == ()
    assert tickers_for_sleeve("nope") == ()


def test_b046_new_sleeves_are_known_but_carry_no_news_universe() -> None:
    """B046 F002 reconcile: the momentum + hk_china sleeves the registry
    gained are recognised by the news layer (so the API stays forgiving),
    but they trade instruments outside the news universe → no constituents
    (graceful empty, no raise) — same posture as the regime sleeve."""

    assert is_known_sleeve("momentum")
    assert is_known_sleeve("satellite_hk_china")
    assert tickers_for_sleeve("momentum") == ()
    assert tickers_for_sleeve("satellite_hk_china") == ()


def test_sleeve_query_text_includes_label_and_tickers() -> None:
    text = build_sleeve_query_text("satellite_us_quality")
    assert text.startswith("satellite us quality ")
    assert "AAPL" in text


def test_sleeve_tickers_module_does_not_import_pandas_or_scripts() -> None:
    """The request-path module must not pull pandas / the ``scripts``
    package — that was the F003 frontend-CI 500 root cause."""

    tree = ast.parse(_SLEEVE_TICKERS_SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert "pandas" not in imported
    assert "scripts" not in imported

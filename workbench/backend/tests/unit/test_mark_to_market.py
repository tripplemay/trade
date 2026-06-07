"""B046 F001 — mark-to-market current-weight helper unit tests.

Pure arithmetic against known closes (no DB): NAV = cash + Σ shares × latest_close,
current_weight = market_value / NAV, with the degrade-don't-crash edges
(unmarked symbol / no positions / NAV<=0 / unheld symbol).
"""

from __future__ import annotations

from collections.abc import Iterable

from workbench_api.services.mark_to_market import (
    compute_mark_to_market,
    latest_close,
    marks_for,
)
from workbench_api.services.prices_provider import PriceMark


class _FakeProvider:
    def __init__(self, marks: dict[str, PriceMark]) -> None:
        self._marks = marks
        self.asked: list[str] = []

    def get_marks(self, symbols: Iterable[str]) -> dict[str, PriceMark]:
        wanted = list(symbols)
        self.asked = sorted(wanted)
        return {s.upper(): self._marks[s.upper()] for s in wanted if s.upper() in self._marks}


def _mark(latest: float, prior: float | None = None) -> PriceMark:
    return PriceMark(latest_close=latest, prior_close=prior if prior is not None else latest)


def test_nav_and_weights_from_known_closes() -> None:
    marks = {"AAPL": _mark(200.0), "MSFT": _mark(400.0)}
    mtm = compute_mark_to_market([("AAPL", 10.0), ("MSFT", 5.0)], cash=1000.0, marks=marks)
    # NAV = 1000 + 10×200 + 5×400 = 5000
    assert mtm.nav == 1000.0 + 2000.0 + 2000.0
    assert mtm.current_weight("AAPL") == 2000.0 / 5000.0
    assert mtm.current_weight("MSFT") == 2000.0 / 5000.0
    assert mtm.by_symbol["AAPL"].market_value == 2000.0
    assert mtm.unmarked == ()


def test_unmarked_symbol_degrades_not_crashes() -> None:
    marks = {"AAPL": _mark(200.0)}  # MSFT has no mark
    mtm = compute_mark_to_market([("AAPL", 10.0), ("MSFT", 5.0)], cash=1000.0, marks=marks)
    # NAV excludes the unmarked MSFT (contributes nothing): 1000 + 2000 = 3000
    assert mtm.nav == 3000.0
    assert "MSFT" in mtm.unmarked
    assert mtm.by_symbol["MSFT"].market_value is None
    assert mtm.current_weight("MSFT") == 0.0
    assert mtm.current_weight("AAPL") == 2000.0 / 3000.0


def test_no_positions_nav_is_cash() -> None:
    mtm = compute_mark_to_market([], cash=2500.0, marks={})
    assert mtm.nav == 2500.0
    assert mtm.by_symbol == {}
    assert mtm.current_weight("ANY") == 0.0


def test_zero_nav_guards_division() -> None:
    # cash 0 + the only position is unmarked → NAV 0 → weight 0.0 (no ZeroDivision).
    mtm = compute_mark_to_market([("X", 10.0)], cash=0.0, marks={})
    assert mtm.nav == 0.0
    assert mtm.current_weight("X") == 0.0


def test_current_weight_unheld_symbol_is_zero() -> None:
    mtm = compute_mark_to_market([("AAPL", 10.0)], cash=0.0, marks={"AAPL": _mark(100.0)})
    assert mtm.current_weight("TSLA") == 0.0


def test_symbol_lookup_is_case_insensitive() -> None:
    mtm = compute_mark_to_market([("aapl", 10.0)], cash=0.0, marks={"AAPL": _mark(100.0)})
    assert mtm.by_symbol["AAPL"].market_value == 1000.0
    assert mtm.current_weight("aapl") == 1.0


def test_latest_close_helper() -> None:
    marks = {"AAPL": _mark(200.0)}
    assert latest_close(marks, "aapl") == 200.0
    assert latest_close(marks, "MSFT") is None


def test_marks_for_dedups_uppercases_skips_empty() -> None:
    provider = _FakeProvider({"AAPL": _mark(200.0)})
    out = marks_for(provider, ["aapl", "AAPL", "", "MSFT"])
    assert out == {"AAPL": _mark(200.0)}
    # Empty string filtered out; symbols upper-cased + de-duplicated.
    assert "" not in provider.asked
    assert set(provider.asked) == {"AAPL", "MSFT"}


def test_marks_for_empty_input_skips_provider() -> None:
    provider = _FakeProvider({"AAPL": _mark(200.0)})
    assert marks_for(provider, []) == {}
    assert provider.asked == []

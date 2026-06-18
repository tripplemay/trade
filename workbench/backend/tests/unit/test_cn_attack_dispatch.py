"""B066 F003 — CN attack registry露出 + dispatch wiring + adapter (offline)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from workbench_api.backtests.adapters import adapt_cn_attack
from workbench_api.backtests.worker import _DISPATCH, INACTIVE_STRATEGY_IDS
from workbench_api.services.strategies import (
    STANDALONE_RESEARCH_STRATEGY_IDS,
    get_strategy,
    list_strategies,
    sleeve_strategies,
)

_CN_ID = "cn_attack_momentum_quality"


class TestRegistry:
    def test_listed_as_research_strategy(self) -> None:
        ids = {s.id for s in list_strategies().strategies}
        assert _CN_ID in ids  # selectable on the backtest page
        detail = get_strategy(_CN_ID)
        assert detail is not None
        assert detail.status == "research"
        assert detail.name  # bilingual display name present
        assert isinstance(detail.config.get("note"), str)  # i18n note resolved

    def test_excluded_from_master_sleeves(self) -> None:
        # A standalone research strategy must NOT materialise a Master sleeve in the
        # home / advisor / risk / news / paper consumers.
        sleeve_ids = {s.id for s in sleeve_strategies()}
        assert _CN_ID not in sleeve_ids
        assert _CN_ID in STANDALONE_RESEARCH_STRATEGY_IDS


class TestDispatch:
    def test_wired_and_runnable(self) -> None:
        # id == dispatch key, and NOT inactive → the worker runs it (not 拒).
        assert _CN_ID in _DISPATCH
        assert _CN_ID not in INACTIVE_STRATEGY_IDS


class _FakeCol:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def tolist(self) -> list[Any]:
        return list(self._values)


class _FakeCurve:
    def __init__(self, dates: list[Any], equities: list[float]) -> None:
        self._cols = {"date": _FakeCol(dates), "equity": _FakeCol(equities)}

    def __getitem__(self, key: str) -> _FakeCol:
        return self._cols[key]


class TestAdapter:
    def test_adapt_cn_attack_maps_equity_and_rebalance_allocations(self) -> None:
        curve = _FakeCurve(
            [date(2025, 8, 1), date(2025, 8, 4), date(2025, 8, 5)],
            [100000.0, 100500.0, 101000.0],
        )
        records = [
            SimpleNamespace(
                date=date(2025, 8, 1),
                rebalanced=True,
                target_tickers=("600519.SH", "000858.SZ", "600036.SH", "300750.SZ"),
            ),
            SimpleNamespace(date=date(2025, 8, 4), rebalanced=False, target_tickers=()),
        ]
        result = SimpleNamespace(equity_curve=curve, daily_records=records)
        mapped = adapt_cn_attack(result)
        assert [row["nav"] for row in mapped["equity"]] == [100000.0, 100500.0, 101000.0]
        # One rebalance day → one allocation row, equal-weighted (1/4 each).
        assert len(mapped["allocations"]) == 1
        weights = mapped["allocations"][0]["weights"]
        assert weights["600519.SH"] == 0.25
        assert mapped["trades"] == []  # engine reports no per-leg fills (honest)

"""B061 F003 — market-aware trading-calendar gap detection.

Covers the spec §9.6 intent: the gap check must not mistake a CN market holiday
for missing data. The core guarantee is the CN-safety regression — a normal
Spring-Festival-week gap is NOT flagged, while a genuine multi-month hole still
is (for both US and CN) — plus the market-detection utilities.
"""

from __future__ import annotations

from datetime import date

import pytest

from trade.data.trading_calendar import (
    market_for_symbol,
    snapshot_market,
    trading_calendar_gaps,
)


class TestMarketForSymbol:
    @pytest.mark.parametrize("symbol", ["AAPL", "SPY", "BRK.B", "^GSPC", "ES=F"])
    def test_us_symbols(self, symbol: str) -> None:
        assert market_for_symbol(symbol) == "US"

    @pytest.mark.parametrize("symbol", ["600519.SH", "000001.SZ", "688981.SH", "300750.sz"])
    def test_cn_symbols(self, symbol: str) -> None:
        assert market_for_symbol(symbol) == "CN"


class TestSnapshotMarket:
    def test_all_cn_is_cn(self) -> None:
        assert snapshot_market(["600519.SH", "000001.SZ"]) == "CN"

    def test_mixed_is_us(self) -> None:
        assert snapshot_market(["AAPL", "600519.SH"]) == "US"

    def test_all_us_is_us(self) -> None:
        assert snapshot_market(["AAPL", "SPY"]) == "US"

    def test_empty_is_us(self) -> None:
        assert snapshot_market([]) == "US"


class TestTradingCalendarGaps:
    def test_empty_and_single_have_no_gaps(self) -> None:
        assert trading_calendar_gaps(()) == ()
        assert trading_calendar_gaps((date(2024, 1, 2),)) == ()

    def test_consecutive_months_no_gap(self) -> None:
        dates = (date(2024, 1, 31), date(2024, 2, 1), date(2024, 3, 1))
        assert trading_calendar_gaps(dates) == ()

    def test_multi_month_hole_is_flagged(self) -> None:
        # The existing US fixture behaviour (test_fixture_loader pins this format).
        dates = (date(2024, 2, 29), date(2024, 4, 30))
        assert trading_calendar_gaps(dates) == ("2024-02-29..2024-04-30",)

    def test_cn_spring_festival_week_is_not_flagged(self) -> None:
        # 2024 Spring Festival closed the A-share market 2024-02-10..2024-02-17;
        # the trading days straddling it are within one month → NOT a gap. This
        # is the §9.6 guarantee: CN holidays are never mistaken for missing data.
        dates = (
            date(2024, 2, 8),
            date(2024, 2, 19),  # first session after the ~9-day holiday
            date(2024, 2, 20),
        )
        assert trading_calendar_gaps(dates) == ()

    def test_cn_year_boundary_holiday_not_flagged(self) -> None:
        # National Day / new-year stretches that cross a month boundary but stay
        # within one month-index step are also safe (≤ 1 month → not flagged).
        dates = (date(2024, 1, 31), date(2024, 2, 19))
        assert trading_calendar_gaps(dates) == ()

    def test_cn_genuine_multi_month_hole_is_flagged(self) -> None:
        # A real CN data hole spanning >1 month IS still surfaced.
        dates = (date(2024, 1, 15), date(2024, 3, 20))
        assert trading_calendar_gaps(dates) == ("2024-01-15..2024-03-20",)

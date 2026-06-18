"""B062 F003 — candidate-universe data-quality checks (§8 deep metrics).

Deterministic + offline: the checks are pure functions over synthetic PriceBar
samples. Covers history depth, adjustment detection, akshare↔baostock
cross-source agreement (<0.5%), suspicious-jump detection, and the aggregate
report verdict flags.
"""

from __future__ import annotations

from datetime import date, timedelta

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.data_quality import (
    SymbolQualityReport,
    adjustment_available,
    assess_symbol,
    count_suspicious_jumps,
    cross_source_deviation,
    cross_source_reanchored_deviation,
    cross_source_return_deviation,
    history_years,
)


def _bar(d: date, close: float, *, adj: float | None = None) -> PriceBar:
    return PriceBar(
        ticker="600519.SH",
        bar_date=d,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        adj_close=adj if adj is not None else close,
        volume=1000,
    )


def _series(n: int, *, start: date = date(2020, 1, 1), step_days: int = 7) -> list[PriceBar]:
    return [_bar(start + timedelta(days=i * step_days), 100.0 + i) for i in range(n)]


class TestHistoryYears:
    def test_span_in_years(self) -> None:
        bars = [_bar(date(2020, 1, 1), 100.0), _bar(date(2024, 1, 1), 120.0)]
        assert history_years(bars) == 4.0

    def test_single_bar_is_none(self) -> None:
        assert history_years([_bar(date(2024, 1, 1), 100.0)]) is None

    def test_empty_is_none(self) -> None:
        assert history_years([]) is None


class TestAdjustment:
    def test_qfq_differs_from_raw_is_available(self) -> None:
        qfq = [_bar(date(2020, 1, 1), 90.0), _bar(date(2020, 1, 2), 91.0)]
        raw = [_bar(date(2020, 1, 1), 100.0), _bar(date(2020, 1, 2), 101.0)]
        assert adjustment_available(qfq, raw) is True

    def test_identical_series_is_not_adjusted(self) -> None:
        same = [_bar(date(2020, 1, 1), 100.0)]
        assert adjustment_available(same, list(same)) is False

    def test_empty_is_none(self) -> None:
        assert adjustment_available([], [_bar(date(2020, 1, 1), 100.0)]) is None


class TestCrossSource:
    def test_agreeing_sources_small_deviation(self) -> None:
        primary = [_bar(date(2024, 1, 1), 100.0), _bar(date(2024, 1, 2), 200.0)]
        secondary = [_bar(date(2024, 1, 1), 100.2), _bar(date(2024, 1, 2), 200.0)]
        overlap, max_dev = cross_source_deviation(primary, secondary)
        assert overlap == 2
        assert max_dev is not None
        assert max_dev < 0.005  # 0.2/100 = 0.2% < 0.5%

    def test_disagreeing_sources_flagged(self) -> None:
        primary = [_bar(date(2024, 1, 1), 100.0)]
        secondary = [_bar(date(2024, 1, 1), 105.0)]
        _, max_dev = cross_source_deviation(primary, secondary)
        assert max_dev is not None
        assert max_dev > 0.005  # 5% > 0.5%

    def test_no_overlap(self) -> None:
        primary = [_bar(date(2024, 1, 1), 100.0)]
        secondary = [_bar(date(2024, 2, 1), 100.0)]
        overlap, max_dev = cross_source_deviation(primary, secondary)
        assert overlap == 0
        assert max_dev is None


class TestAnchorRobustCrossSource:
    """B065 F003 — return + re-anchored lenses isolate the qfq-anchor 口径."""

    @staticmethod
    def _anchor_offset_series(scale: float) -> list[PriceBar]:
        # Same underlying returns (+10%/day), levels scaled by `scale` (a pure
        # front-adjustment-anchor difference, like akshare qfq vs baostock).
        closes = [100.0, 110.0, 121.0, 133.1, 146.41]
        return [
            _bar(date(2024, 1, 1) + timedelta(days=i), c * scale)
            for i, c in enumerate(closes)
        ]

    def test_pure_anchor_offset_huge_level_but_zero_return_and_reanchored(self) -> None:
        primary = self._anchor_offset_series(1.0)
        secondary = self._anchor_offset_series(0.6)  # 40% lower levels, same returns
        _, level_dev = cross_source_deviation(primary, secondary)
        _, return_dev = cross_source_return_deviation(primary, secondary)
        _, reanchored_dev = cross_source_reanchored_deviation(primary, secondary)
        assert level_dev is not None and level_dev > 0.3  # B063-style large level gap
        assert return_dev is not None and return_dev < 1e-9  # returns agree → same underlying
        assert reanchored_dev is not None and reanchored_dev < 1e-9  # 口径 offset only

    def test_genuine_discrepancy_survives_reanchoring(self) -> None:
        primary = self._anchor_offset_series(1.0)
        # Secondary diverges in the MIDDLE (a real data error, not an anchor offset).
        secondary = self._anchor_offset_series(1.0)
        broken = list(secondary)
        broken[2] = _bar(broken[2].bar_date, 200.0)  # genuine bad close
        _, return_dev = cross_source_return_deviation(primary, broken)
        _, reanchored_dev = cross_source_reanchored_deviation(primary, broken)
        assert return_dev is not None and return_dev > 0.005  # real divergence shows
        assert reanchored_dev is not None and reanchored_dev > 0.005

    def test_no_overlap_is_none(self) -> None:
        primary = [_bar(date(2024, 1, 1), 100.0)]
        secondary = [_bar(date(2024, 2, 1), 100.0)]
        assert cross_source_return_deviation(primary, secondary) == (0, None)
        assert cross_source_reanchored_deviation(primary, secondary) == (0, None)


class TestSuspiciousJumps:
    def test_clean_series_has_none(self) -> None:
        assert count_suspicious_jumps(_series(10)) == 0

    def test_big_jump_detected(self) -> None:
        bars = [
            _bar(date(2024, 1, 1), 100.0, adj=100.0),
            _bar(date(2024, 1, 2), 100.0, adj=200.0),  # +100% jump
        ]
        assert count_suspicious_jumps(bars) == 1


class TestAssessSymbol:
    def test_full_report_passes(self) -> None:
        qfq = _series(60)  # ~60 weeks > 1y; span ~1.1y
        baostock = _series(60)  # identical → agree
        raw = _series(60, start=date(2020, 1, 1))
        report = assess_symbol(
            "600519.SH",
            qfq_bars=qfq,
            raw_bars=[_bar(b.bar_date, b.close + 10) for b in raw],  # raw differs → adjusted
            cross_source_bars=baostock,
            history_floor_years=1.0,
        )
        assert isinstance(report, SymbolQualityReport)
        assert report.symbol == "600519.SH"
        assert report.rows == 60
        assert report.meets_history_floor is True
        assert report.adjustment_available is True
        assert report.cross_source_overlap_days == 60
        assert report.cross_source_within_tolerance is True
        # B065 F003 — anchor-robust lenses populated (identical series → agree).
        assert report.cross_source_return_within_tolerance is True
        assert report.cross_source_reanchored_within_tolerance is True
        assert report.suspicious_jumps == 0

    def test_history_floor_not_met(self) -> None:
        report = assess_symbol(
            "0700.HK", qfq_bars=_series(3), history_floor_years=3.0
        )
        assert report.meets_history_floor is False
        # HK has no baostock cross-source → overlap 0, tolerance None.
        assert report.cross_source_overlap_days == 0
        assert report.cross_source_within_tolerance is None
        assert report.adjustment_available is None  # no raw_bars provided

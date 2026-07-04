"""B080 F003 — CPCV-lite split generator (pure)."""

from __future__ import annotations

from datetime import date, timedelta

from workbench_api.monitoring.cpcv import CPCV_LITE_LABEL, cpcv_lite_splits


def test_generates_k_staggered_purged_splits() -> None:
    start, end = date(2019, 4, 1), date(2026, 6, 30)
    splits = cpcv_lite_splits(start, end, k=4)
    assert len(splits) == 4
    # Staggered forward, non-overlapping OOS windows tiling the tail of the span.
    oos_starts = [s.oos_start for s in splits]
    assert oos_starts == sorted(oos_starts)
    assert all(a.oos_end <= b.oos_start for a, b in zip(splits, splits[1:], strict=False))
    # Every fold has a >= ~1-month purge gap between IS end and OOS start.
    for s in splits:
        assert (s.oos_start - s.is_end) >= timedelta(days=30)
        assert s.is_start == start
    # Last fold reaches the span end.
    assert splits[-1].oos_end == end
    assert "not full CPCV" in CPCV_LITE_LABEL


def test_short_span_degrades_to_empty() -> None:
    # Too short to fit a purge gap in each block → [] (caller falls back).
    assert cpcv_lite_splits(date(2026, 1, 1), date(2026, 2, 1), k=4) == []
    assert cpcv_lite_splits(date(2026, 1, 1), date(2026, 1, 1)) == []

"""B083 F001 — PEAD 业绩预告 events PIT-dedup contract.

The IC first-look (F002) enters on the announcement date T+1, so the events must be
PIT: one row per (stock, report period) = the LATEST 公告日期 (final pre-report
forecast), and any row without a parseable announce_date is dropped (can't be
PIT-entered). Guards the exact logic feeding the forward-return rank-IC.
"""

from __future__ import annotations

import pandas as pd

from scripts.research.b083_pead_fetch import pit_dedup


def test_pit_dedup_keeps_latest_announcement_and_drops_undated() -> None:
    raw = pd.DataFrame(
        [
            # 000001 forecast revised: two announcements, same report period.
            {"ticker": "000001", "report_period": "20240930",
             "announce_date": "2024-10-01", "forecast_value": 100, "forecast_type": "预增"},
            {"ticker": "000001", "report_period": "20240930",
             "announce_date": "2024-11-14", "forecast_value": 120, "forecast_type": "预增"},
            {"ticker": "000002", "report_period": "20240930",
             "announce_date": "2024-10-15", "forecast_value": 50, "forecast_type": "略增"},
            # no announce_date → not PIT-enterable → dropped.
            {"ticker": "000003", "report_period": "20240930",
             "announce_date": "", "forecast_value": 10, "forecast_type": "预减"},
        ]
    )
    out = pit_dedup(raw)

    # 000001 deduped to its LATEST announcement; 000002 kept; 000003 dropped (no date).
    assert len(out) == 2
    assert set(out["ticker"]) == {"000001", "000002"}
    row1 = out[out["ticker"] == "000001"].iloc[0]
    assert row1["forecast_value"] == 120  # the later (2024-11-14) revision wins
    assert str(row1["announce_date"].date()) == "2024-11-14"


def test_pit_dedup_separates_report_periods() -> None:
    # Same stock, DIFFERENT report periods → both kept (distinct events).
    raw = pd.DataFrame(
        [
            {"ticker": "000001", "report_period": "20240630",
             "announce_date": "2024-07-14", "forecast_value": 80, "forecast_type": "预增"},
            {"ticker": "000001", "report_period": "20240930",
             "announce_date": "2024-10-14", "forecast_value": 120, "forecast_type": "预增"},
        ]
    )
    out = pit_dedup(raw)
    assert len(out) == 2
    assert set(out["report_period"]) == {"20240630", "20240930"}

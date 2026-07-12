from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "test" / "ashare_quality_sue_first_look.py"
)
_SPEC = importlib.util.spec_from_file_location("ashare_quality_sue_first_look", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
research = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = research
_SPEC.loader.exec_module(research)


def _raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "SECUCODE": "000001.SZ",
        "SECURITY_CODE": "000001",
        "SECURITY_NAME_ABBR": "Sample",
        "REPORTDATE": "2020-03-31",
        "NOTICE_DATE": "2020-04-20",
        "UPDATE_DATE": "2024-09-07",
        "BASIC_EPS": 1.0,
        "PARENT_NETPROFIT": 100.0,
        "WEIGHTAVG_ROE": 10.0,
        "XSMLL": 20.0,
        "MGJYXJJE": 0.5,
        "BOARD_CODE": "BK0001",
        "BOARD_NAME": "Example",
        "TRADE_MARKET_CODE": "069001002001",
        "SECURITY_TYPE_CODE": "058001001",
    }
    row.update(overrides)
    return row


def test_normalize_uses_original_notice_not_later_update() -> None:
    normalized, diagnostics = research.normalize_reports(pd.DataFrame([_raw_row()]))

    assert normalized.loc[0, "notice_date"] == pd.Timestamp("2020-04-20")
    assert normalized.loc[0, "update_date"] == pd.Timestamp("2024-09-07")
    assert normalized.loc[0, "fresh_report"]
    assert diagnostics["parsed_notice_fraction"] == 1.0


def test_quality_constraint_is_contemporaneous_absolute_rule() -> None:
    raw = pd.DataFrame(
        [
            _raw_row(SECUCODE="000001.SZ", WEIGHTAVG_ROE=1, MGJYXJJE=1, XSMLL=np.nan),
            _raw_row(SECUCODE="000002.SZ", SECURITY_CODE="000002", MGJYXJJE=-0.1),
            _raw_row(SECUCODE="000003.SZ", SECURITY_CODE="000003", WEIGHTAVG_ROE=-1),
        ]
    )
    normalized, _ = research.normalize_reports(raw)

    result = normalized.set_index("ticker")["quality_pass"].to_dict()
    assert result == {"000001.SZ": True, "000002.SZ": False, "000003.SZ": False}


def test_sue_scale_uses_only_strictly_prior_unexpected_earnings() -> None:
    discrete = [1.0 + 0.1 * index + (0.2 if index % 4 == 0 else 0.0) for index in range(24)]
    rows = []
    for index, _value in enumerate(discrete):
        year = 2014 + index // 4
        quarter = index % 4 + 1
        cumulative = sum(discrete[index - (quarter - 1) : index + 1])
        report_date = pd.Timestamp(
            year=year,
            month=quarter * 3,
            day=31 if quarter in (1, 4) else 30,
        )
        rows.append(
            {
                "ticker": "000001.SZ",
                "report_date": report_date,
                "notice_date": report_date + pd.Timedelta(days=30),
                "quarter": quarter,
                "period_index": year * 4 + quarter,
                "PARENT_NETPROFIT": cumulative,
            }
        )
    base = pd.DataFrame(rows)
    original = research.build_sue(base)
    target_period = int(original.iloc[-2]["period_index"])
    target_sue = float(original.loc[original["period_index"].eq(target_period), "sue"].iloc[0])

    changed = base.copy()
    changed.loc[changed.index[-1], "PARENT_NETPROFIT"] = 1_000_000.0
    rerun = research.build_sue(changed)
    rerun_target = float(rerun.loc[rerun["period_index"].eq(target_period), "sue"].iloc[0])

    assert np.isfinite(target_sue)
    assert rerun_target == target_sue


def test_sue_excludes_prior_quarter_published_on_same_day() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["000001.SZ", "000001.SZ"],
            "report_date": pd.to_datetime(["2020-03-31", "2020-06-30"]),
            "notice_date": pd.to_datetime(["2020-08-30", "2020-08-30"]),
            "quarter": [1, 2],
            "period_index": [2020 * 4 + 1, 2020 * 4 + 2],
            "PARENT_NETPROFIT": [10.0, 25.0],
        }
    )

    same_day = research.build_sue(frame)
    prior_day = frame.copy()
    prior_day.loc[0, "notice_date"] = pd.Timestamp("2020-08-29")
    prior_available = research.build_sue(prior_day)

    assert np.isnan(same_day.loc[1, "quarter_earnings"])
    assert prior_available.loc[1, "quarter_earnings"] == 15.0


def test_pit_membership_does_not_use_historical_union() -> None:
    schedule = research.UniverseSchedule(
        dates=pd.DatetimeIndex(["2020-03-31", "2020-06-30"]),
        members=(frozenset({"000001.SZ"}), frozenset({"000002.SZ"})),
    )
    events = pd.DataFrame(
        {
            "ticker": ["000001.SZ", "000001.SZ", "000002.SZ"],
            "notice_date": pd.to_datetime(["2020-04-20", "2020-07-20", "2020-07-20"]),
        }
    )

    attached = research.attach_pit_membership(events, schedule)

    assert attached["pit_member"].tolist() == [True, False, True]


def test_price_events_waits_for_tradeable_open_and_n1_is_open_to_close() -> None:
    dates = pd.bdate_range("2019-12-02", periods=90)
    notice_position = 25
    notice_date = dates[notice_position]
    first_after = notice_position + 1
    tradeable = first_after + 2
    close = np.linspace(8.0, 17.0, len(dates))
    open_values = close.copy()
    open_values[tradeable] = 10.0
    close[tradeable] = 11.0
    status = np.ones(len(dates), dtype=int)
    status[first_after:tradeable] = 0
    target_exit = tradeable + 19
    status[target_exit] = 0
    close[target_exit + 1] = 15.0
    prices = pd.DataFrame(
        {
            "date": dates,
            "ticker": "000001.SZ",
            "open": open_values,
            "adj_close": close,
            "volume": 1_000_000.0,
            "tradestatus": status,
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["000001.SZ"],
            "SECURITY_NAME_ABBR": ["Sample"],
            "report_date": [pd.Timestamp("2019-12-31")],
            "notice_date": [notice_date],
            "sue": [2.0],
            "quality_pass": [True],
            "BOARD_NAME": ["Example"],
            "update_lag_days": [0],
        }
    )

    priced = research.price_events(events, prices)

    assert priced.loc[0, "entry_date"] == dates[tradeable]
    assert np.isclose(priced.loc[0, "ret_1"], 0.1)
    assert np.isclose(priced.loc[0, "ret_20"], close[target_exit + 1] / 10.0 - 1.0)
    assert priced.loc[0, "exit_delay_20"] == 1


def test_pit_size_uses_strictly_prior_month_end(tmp_path: Path) -> None:
    size_path = tmp_path / "size.csv"
    pd.DataFrame(
        {
            "data_date": ["2020-01-31", "2020-02-28"],
            "ticker": ["000001.SZ", "000001.SZ"],
            "market_cap": [100.0, 200.0],
        }
    ).to_csv(size_path, index=False)
    events = pd.DataFrame({"ticker": ["000001.SZ"], "entry_date": [pd.Timestamp("2020-02-28")]})

    attached = research.attach_pit_size(events, size_path)

    assert attached.loc[0, "pit_market_cap"] == 100.0


def test_chinext_limit_band_respects_2020_reform_date() -> None:
    assert research._limit_band("300001.SZ", pd.Timestamp("2020-08-21")) == 0.10
    assert research._limit_band("300001.SZ", pd.Timestamp("2020-08-24")) == 0.20
    assert research._limit_band("688001.SH", pd.Timestamp("2019-07-22")) == 0.20


def test_monthly_cross_section_keeps_one_latest_report_per_ticker() -> None:
    tickers = [f"{index:06d}.SZ" for index in range(20)]
    rows = [
        {
            "ticker": ticker,
            "entry_date": pd.Timestamp("2020-04-10"),
            "notice_date": pd.Timestamp("2020-04-09"),
            "report_date": pd.Timestamp("2019-12-31"),
            "sue": float(index),
            "ret_20": float(index) / 100,
        }
        for index, ticker in enumerate(tickers)
    ]
    rows.append(
        {
            "ticker": tickers[0],
            "entry_date": pd.Timestamp("2020-04-30"),
            "notice_date": pd.Timestamp("2020-04-29"),
            "report_date": pd.Timestamp("2020-03-31"),
            "sue": 99.0,
            "ret_20": 0.99,
        }
    )

    cross_section = research._monthly_cross_section(pd.DataFrame(rows), "ret_20")
    monthly = research._monthly_ic_table(pd.DataFrame(rows), "ret_20")

    assert monthly.loc[0, "n"] == 20
    retained = cross_section[cross_section["ticker"].eq(tickers[0])].iloc[0]
    assert retained["report_date"] == pd.Timestamp("2020-03-31")
    assert retained["sue"] == 99.0


def test_block_bootstrap_is_deterministic() -> None:
    values = np.linspace(-0.1, 0.2, 80)
    first = research._block_bootstrap(values)
    second = research._block_bootstrap(values)

    assert first == second


def test_placebo_gate_accepts_exact_zero_and_rejects_missing() -> None:
    assert research._placebo_gate_passes(0.0)
    assert not research._placebo_gate_passes(None)
    assert not research._placebo_gate_passes(float("nan"))
